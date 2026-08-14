"""SQLAlchemy Core coordination for Leader tasks and their durable children."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, exists, insert, select, update

from ...domain.agent_task import AgentTaskAttemptStatus, AgentTaskKind, AgentTaskStatus
from ...domain.evidence_merge import merge_evidence_packets
from .database import begin_runtime_write, create_engine
from .models import agent_task_attempts, agent_task_outbox, agent_tasks
from .runtime_schema import ensure_runtime_schema

_TERMINAL_STATUSES = (
    AgentTaskStatus.COMPLETED.value,
    AgentTaskStatus.FAILED.value,
    AgentTaskStatus.CANCELLED.value,
    AgentTaskStatus.EXPIRED.value,
)
_PARENT_TASKS = agent_tasks.alias("parent_tasks")


def wait_for_child_tasks(*, task_uid: str, attempt_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Release a completed leader attempt while child tasks execute independently."""
    ensure_runtime_schema(db_name)
    now = _timestamp()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            attempt = connection.execute(
                update(agent_task_attempts)
                .where(
                    and_(
                        agent_task_attempts.c.attempt_uid == attempt_uid,
                        agent_task_attempts.c.task_uid == task_uid,
                        agent_task_attempts.c.status == AgentTaskAttemptStatus.RUNNING.value,
                    )
                )
                .values(
                    status=AgentTaskAttemptStatus.COMPLETED.value,
                    result_json=json.dumps({"summary": "waiting_children"}, ensure_ascii=False),
                    finished_at=now,
                )
            )
            if attempt.rowcount != 1:
                return False
            task = connection.execute(
                update(agent_tasks)
                .where(
                    and_(
                        agent_tasks.c.task_uid == task_uid,
                        agent_tasks.c.current_attempt_uid == attempt_uid,
                        agent_tasks.c.status == AgentTaskStatus.RUNNING.value,
                    )
                )
                .values(
                    status=AgentTaskStatus.WAITING_CHILDREN.value,
                    current_attempt_uid=None,
                    updated_at=now,
                )
            )
            return task.rowcount == 1
    finally:
        engine.dispose()


def has_nonterminal_child_tasks(*, parent_task_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Return whether a parent has any child that is not terminal."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            return connection.execute(
                select(agent_tasks.c.task_uid)
                .where(
                    and_(
                        agent_tasks.c.parent_task_uid == parent_task_uid,
                        agent_tasks.c.status.not_in(_TERMINAL_STATUSES),
                    )
                )
                .limit(1)
            ).first() is not None
    finally:
        engine.dispose()


def create_join_continuation_if_ready(
    *, child_task_uid: str, db_name: str = "./database.sqlite"
) -> tuple[dict[str, Any] | None, bool]:
    """Create exactly one continuation once a waiting leader has no active children."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            child = connection.execute(
                select(agent_tasks.c.parent_task_uid).where(agent_tasks.c.task_uid == child_task_uid)
            ).first()
            if child is None or not child._mapping["parent_task_uid"]:
                return None, False
            parent_uid = str(child._mapping["parent_task_uid"])
            parent = connection.execute(
                select(agent_tasks).where(
                    and_(
                        agent_tasks.c.task_uid == parent_uid,
                        agent_tasks.c.status == AgentTaskStatus.WAITING_CHILDREN.value,
                    )
                )
            ).first()
            if parent is None or _has_active_subagent(connection, parent_uid):
                return None, False
            existing = connection.execute(
                select(agent_tasks)
                .where(
                    and_(
                        agent_tasks.c.parent_task_uid == parent_uid,
                        agent_tasks.c.kind == AgentTaskKind.CONTINUATION.value,
                    )
                )
                .order_by(agent_tasks.c.created_at, agent_tasks.c.task_uid)
                .limit(1)
            ).first()
            if existing is not None:
                return _task_from_row(existing), False
            parent_data = parent._mapping
            epoch = int(parent_data["continuation_epoch"]) + 1
            now = _timestamp()
            continuation_uid = f"task_{uuid.uuid4().hex}"
            connection.execute(
                insert(agent_tasks).values(
                    task_uid=continuation_uid,
                    run_uid=str(parent_data["run_uid"]),
                    parent_task_uid=parent_uid,
                    parent_task_key=parent_uid,
                    kind=AgentTaskKind.CONTINUATION.value,
                    agent_role="",
                    status=AgentTaskStatus.QUEUED.value,
                    idempotency_key=f"join:{epoch}",
                    continuation_epoch=epoch,
                    input_json=json.dumps(
                        _continuation_input(connection, parent_uid),
                        ensure_ascii=False,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                update(agent_tasks)
                .where(agent_tasks.c.task_uid == parent_uid)
                .values(continuation_epoch=epoch, updated_at=now)
            )
            connection.execute(
                insert(agent_task_outbox).values(
                    outbox_uid=f"outbox_{uuid.uuid4().hex}",
                    task_uid=continuation_uid,
                    event_type="task.dispatch_requested",
                    payload_json=json.dumps({"task_uid": continuation_uid}),
                    status="pending",
                    available_at=now,
                    created_at=now,
                )
            )
            continuation = connection.execute(
                select(agent_tasks).where(agent_tasks.c.task_uid == continuation_uid)
            ).one()
            return _task_from_row(continuation), True
    finally:
        engine.dispose()


def complete_waiting_parent_task(
    *, parent_task_uid: str, continuation_task_uid: str, db_name: str = "./database.sqlite"
) -> bool:
    """Complete a waiting leader only from its completed own continuation."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            completed_continuation = exists(
                select(agent_tasks.c.task_uid).where(
                    and_(
                        agent_tasks.c.task_uid == continuation_task_uid,
                        agent_tasks.c.parent_task_uid == parent_task_uid,
                        agent_tasks.c.kind == AgentTaskKind.CONTINUATION.value,
                        agent_tasks.c.status == AgentTaskStatus.COMPLETED.value,
                    )
                )
            )
            updated = connection.execute(
                update(agent_tasks)
                .where(
                    and_(
                        agent_tasks.c.task_uid == parent_task_uid,
                        agent_tasks.c.status == AgentTaskStatus.WAITING_CHILDREN.value,
                        completed_continuation,
                    )
                )
                .values(status=AgentTaskStatus.COMPLETED.value, finished_at=_timestamp(), updated_at=_timestamp())
            )
            return updated.rowcount == 1
    finally:
        engine.dispose()


def reconcile_waiting_child_joins(*, db_name: str = "./database.sqlite") -> list[str]:
    """Create continuation records missed across a cancellation or crash boundary."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_tasks.c.task_uid)
                .join(_PARENT_TASKS, _PARENT_TASKS.c.task_uid == agent_tasks.c.parent_task_uid)
                .where(
                    and_(
                        agent_tasks.c.kind == AgentTaskKind.SUBAGENT.value,
                        _PARENT_TASKS.c.status == AgentTaskStatus.WAITING_CHILDREN.value,
                    )
                )
            ).all()
    finally:
        engine.dispose()
    created: list[str] = []
    for row in rows:
        continuation, did_create = create_join_continuation_if_ready(
            child_task_uid=str(row._mapping["task_uid"]), db_name=db_name
        )
        if did_create and continuation is not None:
            created.append(str(continuation["task_uid"]))
    return created


def reconcile_completed_continuation_parents(*, db_name: str = "./database.sqlite") -> list[str]:
    """Close waiting leaders whose continuation committed before a worker crashed."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_tasks.c.parent_task_uid, agent_tasks.c.task_uid)
                .where(
                    and_(
                        agent_tasks.c.kind == AgentTaskKind.CONTINUATION.value,
                        agent_tasks.c.status == AgentTaskStatus.COMPLETED.value,
                    )
                )
                .order_by(agent_tasks.c.finished_at, agent_tasks.c.task_uid)
            ).all()
    finally:
        engine.dispose()
    completed: list[str] = []
    for row in rows:
        parent_uid = row._mapping["parent_task_uid"]
        if parent_uid and complete_waiting_parent_task(
            parent_task_uid=str(parent_uid),
            continuation_task_uid=str(row._mapping["task_uid"]),
            db_name=db_name,
        ):
            completed.append(str(parent_uid))
    return completed


def _has_active_subagent(connection: Any, parent_task_uid: str) -> bool:
    return connection.execute(
        select(agent_tasks.c.task_uid)
        .where(
            and_(
                agent_tasks.c.parent_task_uid == parent_task_uid,
                agent_tasks.c.kind == AgentTaskKind.SUBAGENT.value,
                agent_tasks.c.status.not_in(_TERMINAL_STATUSES),
            )
        )
        .limit(1)
    ).first() is not None


def _child_results(connection: Any, parent_task_uid: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            agent_tasks.c.task_uid,
            agent_tasks.c.agent_role,
            agent_tasks.c.status,
            agent_tasks.c.input_json,
            agent_tasks.c.result_json,
            agent_tasks.c.error_message,
        )
        .where(
            and_(
                agent_tasks.c.parent_task_uid == parent_task_uid,
                agent_tasks.c.kind == AgentTaskKind.SUBAGENT.value,
            )
        )
        .order_by(agent_tasks.c.created_at, agent_tasks.c.task_uid)
    ).all()
    return [
        {
            "task_uid": str(row._mapping["task_uid"]),
            "role": str(row._mapping["agent_role"]),
            "status": str(row._mapping["status"]),
            "tool_call_id": str(json.loads(row._mapping["input_json"]).get("tool_call_id") or ""),
            "packet": json.loads(row._mapping["result_json"]),
            "error_message": str(row._mapping["error_message"] or ""),
        }
        for row in rows
    ]


def _continuation_input(connection: Any, parent_task_uid: str) -> dict[str, Any]:
    tool_results = _child_results(connection, parent_task_uid)
    return {
        "parent_task_uid": parent_task_uid,
        "tool_results": tool_results,
        "evidence_merge": merge_evidence_packets(tool_results),
    }


def _task_from_row(row: Any) -> dict[str, Any]:
    task = dict(row._mapping)
    task["input"] = json.loads(task.pop("input_json"))
    task["result"] = json.loads(task.pop("result_json"))
    return task


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "complete_waiting_parent_task",
    "create_join_continuation_if_ready",
    "has_nonterminal_child_tasks",
    "reconcile_completed_continuation_parents",
    "reconcile_waiting_child_joins",
    "wait_for_child_tasks",
]
