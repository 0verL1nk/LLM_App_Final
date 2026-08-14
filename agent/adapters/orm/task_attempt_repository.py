"""SQLAlchemy Core lease lifecycle for durable AgentTask attempts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, exists, func, insert, select, update

from ...domain.agent_task import AgentTaskAttemptStatus, AgentTaskStatus
from .database import begin_runtime_write, create_engine
from .models import agent_task_attempts, agent_task_outbox, agent_tasks
from .research_plan_repository import (
    task_is_runnable_in_transaction,
    transition_linked_plan_step_in_transaction,
)
from .runtime_schema import ensure_runtime_schema


def claim_next_task(*, worker_id: str, lease_seconds: float = 60.0, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Lease the oldest runnable task and create its owner attempt."""
    return _claim_task(worker_id=worker_id, lease_seconds=lease_seconds, db_name=db_name)


def claim_task_by_uid(*, task_uid: str, worker_id: str, lease_seconds: float = 60.0, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Lease one queue-addressed task; duplicate delivery cannot execute it twice."""
    normalized_task_uid = task_uid.strip()
    if not normalized_task_uid:
        raise ValueError("Task UID is required")
    return _claim_task(worker_id=worker_id, lease_seconds=lease_seconds, task_uid=normalized_task_uid, db_name=db_name)


def mark_task_running(*, task_uid: str, attempt_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Transition the current leased task and attempt to running together."""
    ensure_runtime_schema(db_name)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            task = connection.execute(
                update(agent_tasks)
                .where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid, agent_tasks.c.status == AgentTaskStatus.LEASED.value))
                .values(status=AgentTaskStatus.RUNNING.value, updated_at=timestamp)
            )
            if task.rowcount != 1:
                return False
            transition_linked_plan_step_in_transaction(connection, task_uid=task_uid, status=AgentTaskStatus.RUNNING.value)
            attempt = connection.execute(
                update(agent_task_attempts)
                .where(and_(agent_task_attempts.c.attempt_uid == attempt_uid, agent_task_attempts.c.task_uid == task_uid, agent_task_attempts.c.status == AgentTaskAttemptStatus.LEASED.value))
                .values(status=AgentTaskAttemptStatus.RUNNING.value, started_at=timestamp, heartbeat_at=timestamp)
            )
            return attempt.rowcount == 1
    finally:
        engine.dispose()


def heartbeat_task_attempt(*, task_uid: str, attempt_uid: str, lease_seconds: float = 60.0, db_name: str = "./database.sqlite") -> bool:
    """Extend an active lease only while the attempt remains the current owner."""
    ensure_runtime_schema(db_name)
    heartbeat_at = datetime.now(UTC)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            updated = connection.execute(
                update(agent_task_attempts)
                .where(
                    and_(
                        agent_task_attempts.c.attempt_uid == attempt_uid,
                        agent_task_attempts.c.task_uid == task_uid,
                        agent_task_attempts.c.status.in_((AgentTaskAttemptStatus.LEASED.value, AgentTaskAttemptStatus.RUNNING.value)),
                        exists(
                            select(agent_tasks.c.task_uid).where(
                                and_(
                                    agent_tasks.c.task_uid == task_uid,
                                    agent_tasks.c.current_attempt_uid == attempt_uid,
                                )
                            )
                        ),
                    )
                )
                .values(heartbeat_at=heartbeat_at.isoformat(), lease_expires_at=_expires_at(heartbeat_at, lease_seconds))
            )
            return updated.rowcount == 1
    finally:
        engine.dispose()


def complete_task_attempt(*, task_uid: str, attempt_uid: str, result: dict[str, Any] | None = None, error_message: str = "", db_name: str = "./database.sqlite") -> bool:
    """Complete the owned attempt; cancellation and late-result protection win races."""
    ensure_runtime_schema(db_name)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            task = connection.execute(
                select(agent_tasks.c.cancel_requested_at).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid))
            ).first()
            if task is None:
                return False
            cancelled = bool(task._mapping["cancel_requested_at"])
            succeeded = not error_message.strip() and not cancelled
            task_status = AgentTaskStatus.COMPLETED if succeeded else AgentTaskStatus.CANCELLED if cancelled else AgentTaskStatus.FAILED
            attempt_status = AgentTaskAttemptStatus.COMPLETED if succeeded else AgentTaskAttemptStatus.CANCELLED if cancelled else AgentTaskAttemptStatus.FAILED
            attempt = connection.execute(
                update(agent_task_attempts)
                .where(and_(agent_task_attempts.c.attempt_uid == attempt_uid, agent_task_attempts.c.task_uid == task_uid, agent_task_attempts.c.status.in_((AgentTaskAttemptStatus.LEASED.value, AgentTaskAttemptStatus.RUNNING.value))))
                .values(status=attempt_status.value, finished_at=timestamp, result_json=json.dumps(result or {}, ensure_ascii=False), error_message=error_message.strip()[:1000])
            )
            if attempt.rowcount != 1:
                return False
            values: dict[str, Any] = {"status": task_status.value, "current_attempt_uid": None, "finished_at": timestamp, "updated_at": timestamp}
            if succeeded:
                values.update({"result_json": json.dumps(result or {}, ensure_ascii=False), "error_message": ""})
            task_update = connection.execute(
                update(agent_tasks)
                .where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid))
                .values(**values)
            )
            if task_update.rowcount == 1:
                transition_linked_plan_step_in_transaction(connection, task_uid=task_uid, status=task_status.value)
            return task_update.rowcount == 1
    finally:
        engine.dispose()


def fail_or_retry_task_attempt(*, task_uid: str, attempt_uid: str, error_category: str, error_message: str, max_attempts: int, db_name: str = "./database.sqlite") -> str:
    """Record one failure, then terminally fail or enqueue an exponential-backoff retry."""
    ensure_runtime_schema(db_name)
    timestamp = datetime.now(UTC)
    now_text = timestamp.isoformat()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            task = connection.execute(
                select(agent_tasks).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid))
            ).first()
            attempt_row = connection.execute(
                select(agent_task_attempts).where(and_(agent_task_attempts.c.attempt_uid == attempt_uid, agent_task_attempts.c.task_uid == task_uid))
            ).first()
            if task is None or attempt_row is None:
                return "lost_lease"
            task_data = task._mapping
            attempt_data = attempt_row._mapping
            if str(attempt_data["status"]) not in {AgentTaskAttemptStatus.LEASED.value, AgentTaskAttemptStatus.RUNNING.value}:
                return "lost_lease"
            cancelled = bool(task_data["cancel_requested_at"])
            connection.execute(
                update(agent_task_attempts)
                .where(agent_task_attempts.c.attempt_uid == attempt_uid)
                .values(status=AgentTaskAttemptStatus.CANCELLED.value if cancelled else AgentTaskAttemptStatus.FAILED.value, finished_at=now_text, error_category=error_category[:80], error_message=error_message[:1000])
            )
            if cancelled:
                connection.execute(update(agent_tasks).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid)).values(status=AgentTaskStatus.CANCELLED.value, current_attempt_uid=None, finished_at=now_text, updated_at=now_text))
                transition_linked_plan_step_in_transaction(connection, task_uid=task_uid, status=AgentTaskStatus.CANCELLED.value)
                return "cancelled"
            attempt_number = int(attempt_data["attempt_number"])
            if attempt_number >= max(1, max_attempts):
                connection.execute(update(agent_tasks).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid)).values(status=AgentTaskStatus.FAILED.value, current_attempt_uid=None, error_message=error_message[:1000], finished_at=now_text, updated_at=now_text))
                transition_linked_plan_step_in_transaction(connection, task_uid=task_uid, status=AgentTaskStatus.FAILED.value)
                return "failed"
            delay_seconds = min(300, 2 ** max(0, attempt_number - 1))
            connection.execute(update(agent_tasks).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid)).values(status=AgentTaskStatus.QUEUED.value, current_attempt_uid=None, error_message=error_message[:1000], updated_at=now_text))
            connection.execute(insert(agent_task_outbox).values(outbox_uid=f"outbox_{uuid.uuid4().hex}", task_uid=task_uid, event_type="task.dispatch_requested", payload_json=json.dumps({"task_uid": task_uid, "retry": attempt_number + 1}), status="pending", available_at=(timestamp + timedelta(seconds=delay_seconds)).isoformat(), created_at=now_text))
            return "retrying"
    finally:
        engine.dispose()


def reclaim_expired_task_attempts(*, now: datetime | None = None, db_name: str = "./database.sqlite") -> list[str]:
    """Expire stale owners and return non-cancelled tasks to the runnable state."""
    ensure_runtime_schema(db_name)
    cutoff = _now(now)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            rows = connection.execute(
                select(agent_tasks.c.task_uid, agent_tasks.c.current_attempt_uid, agent_tasks.c.cancel_requested_at)
                .join(agent_task_attempts, agent_task_attempts.c.attempt_uid == agent_tasks.c.current_attempt_uid)
                .where(and_(agent_tasks.c.status.in_((AgentTaskStatus.LEASED.value, AgentTaskStatus.RUNNING.value)), agent_task_attempts.c.status.in_((AgentTaskAttemptStatus.LEASED.value, AgentTaskAttemptStatus.RUNNING.value)), agent_task_attempts.c.lease_expires_at < cutoff))
            ).all()
            reclaimed: list[str] = []
            for row in rows:
                task_uid = str(row._mapping["task_uid"])
                attempt_uid = str(row._mapping["current_attempt_uid"])
                connection.execute(update(agent_task_attempts).where(and_(agent_task_attempts.c.attempt_uid == attempt_uid, agent_task_attempts.c.status.in_((AgentTaskAttemptStatus.LEASED.value, AgentTaskAttemptStatus.RUNNING.value)))).values(status=AgentTaskAttemptStatus.EXPIRED.value, finished_at=cutoff, error_category="lease_expired", error_message="Worker lease expired"))
                task_status = AgentTaskStatus.CANCELLED.value if row._mapping["cancel_requested_at"] else AgentTaskStatus.QUEUED.value
                connection.execute(update(agent_tasks).where(and_(agent_tasks.c.task_uid == task_uid, agent_tasks.c.current_attempt_uid == attempt_uid)).values(status=task_status, current_attempt_uid=None, updated_at=cutoff))
                if task_status == AgentTaskStatus.CANCELLED.value:
                    transition_linked_plan_step_in_transaction(connection, task_uid=task_uid, status=task_status)
                reclaimed.append(task_uid)
            return reclaimed
    finally:
        engine.dispose()


def _claim_task(*, worker_id: str, lease_seconds: float, db_name: str, task_uid: str | None = None) -> dict[str, Any] | None:
    ensure_runtime_schema(db_name)
    worker = worker_id.strip()
    if not worker:
        raise ValueError("Worker ID is required")
    claimed_at = datetime.now(UTC)
    now_text = claimed_at.isoformat()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            criteria = [agent_tasks.c.status == AgentTaskStatus.QUEUED.value, agent_tasks.c.cancel_requested_at.is_(None)]
            if task_uid is not None:
                criteria.append(agent_tasks.c.task_uid == task_uid)
            candidates = connection.execute(select(agent_tasks.c.task_uid).where(and_(*criteria)).order_by(agent_tasks.c.created_at, agent_tasks.c.task_uid)).scalars()
            candidate = next((task_id for task_id in candidates if task_is_runnable_in_transaction(connection, task_uid=str(task_id))), None)
            if candidate is None:
                return None
            attempt_uid = f"attempt_{uuid.uuid4().hex}"
            claimed = connection.execute(update(agent_tasks).where(and_(agent_tasks.c.task_uid == candidate, agent_tasks.c.status == AgentTaskStatus.QUEUED.value, agent_tasks.c.cancel_requested_at.is_(None))).values(status=AgentTaskStatus.LEASED.value, current_attempt_uid=attempt_uid, started_at=func.coalesce(agent_tasks.c.started_at, now_text), updated_at=now_text))
            if claimed.rowcount != 1:
                return None
            transition_linked_plan_step_in_transaction(connection, task_uid=str(candidate), status=AgentTaskStatus.LEASED.value)
            attempt_number = int(connection.execute(select(func.coalesce(func.max(agent_task_attempts.c.attempt_number), 0) + 1).where(agent_task_attempts.c.task_uid == candidate)).scalar_one())
            connection.execute(insert(agent_task_attempts).values(attempt_uid=attempt_uid, task_uid=candidate, worker_id=worker, attempt_number=attempt_number, status=AgentTaskAttemptStatus.LEASED.value, lease_expires_at=_expires_at(claimed_at, lease_seconds), heartbeat_at=now_text, result_json="{}"))
            task = connection.execute(select(agent_tasks).where(agent_tasks.c.task_uid == candidate)).one()
            return _task_from_row(task)
    finally:
        engine.dispose()


def _task_from_row(row: Any) -> dict[str, Any]:
    task = dict(row._mapping)
    task["input"] = json.loads(task.pop("input_json"))
    task["result"] = json.loads(task.pop("result_json"))
    return task


def _now(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat()


def _expires_at(now: datetime, lease_seconds: float) -> str:
    return (now + timedelta(seconds=max(1.0, lease_seconds))).isoformat()


__all__ = ["claim_next_task", "claim_task_by_uid", "complete_task_attempt", "fail_or_retry_task_attempt", "heartbeat_task_attempt", "mark_task_running", "reclaim_expired_task_attempts"]
