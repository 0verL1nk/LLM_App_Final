"""SQLAlchemy Core task reads, cancellation, and retry operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select, update

from ...domain.agent_task import TERMINAL_TASK_STATUSES, AgentTaskStatus
from .database import create_engine
from .models import agent_runs, agent_task_attempts, agent_tasks
from .runtime_schema import ensure_runtime_schema
from .task_dispatch_repository import create_agent_task


def get_agent_task(*, task_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read one task projection."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(select(agent_tasks).where(agent_tasks.c.task_uid == task_uid)).first()
            return _task_from_row(row) if row is not None else None
    finally:
        engine.dispose()


def get_agent_task_run_context(*, task_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read task scope from its Run rather than queue-supplied input."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(
                    agent_tasks,
                    agent_runs.c.project_uid,
                    agent_runs.c.session_uid,
                    agent_runs.c.uuid.label("user_uuid"),
                    agent_runs.c.prompt.label("run_prompt"),
                )
                .join(agent_runs, agent_runs.c.run_uid == agent_tasks.c.run_uid)
                .where(agent_tasks.c.task_uid == task_uid)
            ).first()
            return _task_from_row(row) if row is not None else None
    finally:
        engine.dispose()


def list_agent_task_attempts(*, task_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Read attempts in execution order for diagnostics and task detail UI."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_task_attempts)
                .where(agent_task_attempts.c.task_uid == task_uid)
                .order_by(agent_task_attempts.c.attempt_number)
            ).all()
            return [_attempt_from_row(row) for row in rows]
    finally:
        engine.dispose()


def request_task_cancel(*, task_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Record cancellation while preserving terminal task history."""
    ensure_runtime_schema(db_name)
    terminal = tuple(status.value for status in TERMINAL_TASK_STATUSES)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            updated = connection.execute(
                update(agent_tasks)
                .where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.status.not_in(terminal)))
                .values(
                    cancel_requested_at=agent_tasks.c.cancel_requested_at,
                    status=agent_tasks.c.status,
                    updated_at=timestamp,
                )
            )
            if updated.rowcount != 1:
                return False
            task = connection.execute(select(agent_tasks).where(agent_tasks.c.task_uid == task_uid)).one()
            values: dict[str, Any] = {"cancel_requested_at": task._mapping["cancel_requested_at"] or timestamp, "updated_at": timestamp}
            if str(task._mapping["status"]) == AgentTaskStatus.QUEUED.value:
                values.update({"status": AgentTaskStatus.CANCELLED.value, "finished_at": timestamp})
            connection.execute(update(agent_tasks).where(agent_tasks.c.task_uid == task_uid).values(**values))
            return True
    finally:
        engine.dispose()


def request_run_cancel(*, run_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Cancel queued task work and request safe-boundary cancellation for active attempts."""
    ensure_runtime_schema(db_name)
    terminal = tuple(status.value for status in TERMINAL_TASK_STATUSES)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            run = connection.execute(select(agent_runs.c.status).where(agent_runs.c.run_uid == run_uid)).first()
            if run is None or str(run._mapping["status"]) not in {"queued", "running"}:
                return False
            connection.execute(
                update(agent_tasks)
                .where(and_(agent_tasks.c.run_uid == run_uid, agent_tasks.c.status.not_in(terminal)))
                .values(cancel_requested_at=timestamp, updated_at=timestamp)
            )
            connection.execute(
                update(agent_tasks)
                .where(and_(agent_tasks.c.run_uid == run_uid, agent_tasks.c.status == AgentTaskStatus.QUEUED.value))
                .values(status=AgentTaskStatus.CANCELLED.value, finished_at=timestamp)
            )
            updated = connection.execute(
                update(agent_runs)
                .where(and_(agent_runs.c.run_uid == run_uid, agent_runs.c.status.in_(("queued", "running"))))
                .values(status="cancelled", error_message="", updated_at=timestamp)
            )
            return updated.rowcount == 1
    finally:
        engine.dispose()


def retry_agent_task(*, task_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any]:
    """Create a new queued task without rewriting failed or cancelled history."""
    original = get_agent_task(task_uid=task_uid, db_name=db_name)
    if original is None:
        raise LookupError("Task not found")
    retryable = {AgentTaskStatus.FAILED.value, AgentTaskStatus.CANCELLED.value, AgentTaskStatus.EXPIRED.value}
    if str(original["status"]) not in retryable:
        raise ValueError("Only terminal unsuccessful tasks can be retried")
    attempts = list_agent_task_attempts(task_uid=task_uid, db_name=db_name)
    task, _ = create_agent_task(
        run_uid=str(original["run_uid"]),
        parent_task_uid=str(original["parent_task_uid"] or "") or None,
        kind=str(original["kind"]),
        agent_role=str(original["agent_role"]),
        idempotency_key=f"retry:{task_uid}:{len(attempts) + 1}",
        input_payload=dict(original["input"]),
        continuation_epoch=int(original["continuation_epoch"]),
        db_name=db_name,
    )
    return task


def _task_from_row(row: Any) -> dict[str, Any]:
    task = dict(row._mapping)
    task["input"] = json.loads(task.pop("input_json"))
    task["result"] = json.loads(task.pop("result_json"))
    return task


def _attempt_from_row(row: Any) -> dict[str, Any]:
    attempt = dict(row._mapping)
    attempt["result"] = json.loads(attempt.pop("result_json"))
    return attempt


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "get_agent_task",
    "get_agent_task_run_context",
    "list_agent_task_attempts",
    "request_run_cancel",
    "request_task_cancel",
    "retry_agent_task",
]
