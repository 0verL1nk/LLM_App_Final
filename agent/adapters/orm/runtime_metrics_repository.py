"""Ownership-scoped operational metrics derived from durable runtime facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from .database import create_engine
from .models import agent_runs, agent_task_attempts, agent_tasks
from .runtime_schema import ensure_runtime_schema


def get_runtime_metrics(
    *, user_uuid: str, stalled_after_seconds: float = 300.0, db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    """Summarize durable runs/tasks without inventing metrics absent from storage."""
    ensure_runtime_schema(db_name)
    cutoff = datetime.now(UTC).timestamp() - max(1.0, stalled_after_seconds)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            runs = connection.execute(select(agent_runs.c.status, agent_runs.c.updated_at).where(agent_runs.c.uuid == user_uuid)).all()
            tasks = connection.execute(
                select(agent_tasks.c.kind, agent_tasks.c.status)
                .join(agent_runs, agent_runs.c.run_uid == agent_tasks.c.run_uid)
                .where(agent_runs.c.uuid == user_uuid)
            ).all()
            attempts = connection.execute(
                select(agent_task_attempts.c.started_at, agent_task_attempts.c.finished_at)
                .join(agent_tasks, agent_tasks.c.task_uid == agent_task_attempts.c.task_uid)
                .join(agent_runs, agent_runs.c.run_uid == agent_tasks.c.run_uid)
                .where(agent_runs.c.uuid == user_uuid)
            ).all()
    finally:
        engine.dispose()
    run_counts = _counts(str(row._mapping["status"]) for row in runs)
    task_counts = _counts(str(row._mapping["status"]) for row in tasks)
    latencies = sorted(_latency_ms(str(row._mapping["started_at"] or ""), str(row._mapping["finished_at"] or "")) for row in attempts)
    valid_latencies = [value for value in latencies if value is not None]
    return {
        "runs": run_counts,
        "tasks": task_counts,
        "delegation_count": sum(1 for row in tasks if str(row._mapping["kind"]) == "subagent"),
        "stalled_runs": sum(1 for row in runs if str(row._mapping["status"]) in {"queued", "running", "waiting_children"} and _timestamp(str(row._mapping["updated_at"])) < cutoff),
        "median_task_latency_ms": _median(valid_latencies),
        "duplicate_delivery_rejections": None,
        "note": "Duplicate queue deliveries are lease-rejected but are not yet counted as a persisted metric.",
    }


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _latency_ms(started_at: str, finished_at: str) -> float | None:
    if not started_at or not finished_at:
        return None
    started = _timestamp(started_at)
    finished = _timestamp(finished_at)
    return max(0.0, (finished - started) * 1000) if started and finished else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


__all__ = ["get_runtime_metrics"]
