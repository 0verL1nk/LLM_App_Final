"""Whole-database baseline metrics for the durable research runtime.

Unlike ``runtime_metrics_repository`` (ownership-scoped API metrics), these
functions read every row of a runtime database to produce the migration
baseline report: run success/failure, stalled runs, delegation volume,
duplicate event occurrences, reconnect recovery and task latency. The report
is a read-only diagnostic; it never mutates runtime state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from .database import create_engine
from .models import agent_run_events, agent_runs, agent_task_attempts, agent_tasks
from .runtime_schema import ensure_runtime_schema

_ACTIVE_RUN_STATUSES = ("queued", "running", "waiting_children")
_TERMINAL_RUN_EVENT_TYPES = ("run.started", "run.completed", "run.failed", "run.cancelled")
_TERMINAL_ITEM_EVENT_TYPES = ("item.completed", "item.failed", "item.cancelled")


def get_baseline_metrics(
    *, db_name: str = "./database.sqlite", stalled_after_seconds: float = 300.0
) -> dict[str, Any]:
    """Compute the migration baseline report from durable runtime tables."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            run_rows = connection.execute(select(agent_runs.c.run_uid, agent_runs.c.status, agent_runs.c.updated_at)).all()
            task_kinds = connection.execute(select(agent_tasks.c.kind, agent_tasks.c.status)).all()
            attempt_rows = connection.execute(
                select(agent_task_attempts.c.started_at, agent_task_attempts.c.finished_at)
            ).all()
            duplicate_lifecycle = connection.execute(
                select(agent_run_events.c.run_uid, agent_run_events.c.event_type, func.count().label("occurrences"))
                .where(agent_run_events.c.event_type.in_(_TERMINAL_RUN_EVENT_TYPES))
                .group_by(agent_run_events.c.run_uid, agent_run_events.c.event_type)
                .having(func.count() > 1)
            ).all()
            duplicate_item_terminals = connection.execute(
                select(agent_run_events.c.run_uid, agent_run_events.c.item_uid, func.count().label("occurrences"))
                .where(
                    agent_run_events.c.event_type.in_(_TERMINAL_ITEM_EVENT_TYPES),
                    agent_run_events.c.item_uid.isnot(None),
                )
                .group_by(agent_run_events.c.run_uid, agent_run_events.c.item_uid)
                .having(func.count() > 1)
            ).all()
            resumed_runs = connection.execute(
                select(agent_run_events.c.run_uid).where(agent_run_events.c.event_type == "run.resumed")
            ).all()
            event_total = connection.execute(select(func.count()).select_from(agent_run_events)).scalar_one()
    finally:
        engine.dispose()

    run_status_counts = _counts(str(row._mapping["status"]) for row in run_rows)
    task_status_counts = _counts(str(row._mapping["status"]) for row in task_kinds)
    cutoff = datetime.now(UTC).timestamp() - max(1.0, stalled_after_seconds)
    stalled = sum(
        1
        for row in run_rows
        if str(row._mapping["status"]) in _ACTIVE_RUN_STATUSES
        and _timestamp(str(row._mapping["updated_at"] or "")) < cutoff
    )
    resumed_ids = {str(row._mapping["run_uid"]) for row in resumed_runs}
    resumed_statuses = _counts(
        str(row._mapping["status"]) for row in run_rows if str(row._mapping["run_uid"]) in resumed_ids
    )
    latencies = sorted(
        value
        for value in (
            _latency_ms(str(row._mapping["started_at"] or ""), str(row._mapping["finished_at"] or ""))
            for row in attempt_rows
        )
        if value is not None
    )
    completed = run_status_counts.get("completed", 0)
    terminal_runs = sum(run_status_counts.get(status, 0) for status in ("completed", "failed", "cancelled"))
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": db_name,
        "stalled_after_seconds": max(1.0, stalled_after_seconds),
        "runs": {
            "total": len(run_rows),
            "status_counts": run_status_counts,
            "success_rate": round(completed / terminal_runs, 4) if terminal_runs else None,
            "stalled": stalled,
        },
        "tasks": {
            "total": len(task_kinds),
            "status_counts": task_status_counts,
            "delegation_count": sum(1 for row in task_kinds if str(row._mapping["kind"]) == "subagent"),
        },
        "events": {
            "total": int(event_total),
            "duplicate_lifecycle_events": [
                {
                    "run_uid": str(row._mapping["run_uid"]),
                    "event_type": str(row._mapping["event_type"]),
                    "occurrences": int(row._mapping["occurrences"]),
                }
                for row in duplicate_lifecycle
            ],
            "duplicate_item_terminal_events": [
                {
                    "run_uid": str(row._mapping["run_uid"]),
                    "item_uid": str(row._mapping["item_uid"]),
                    "occurrences": int(row._mapping["occurrences"]),
                }
                for row in duplicate_item_terminals
            ],
        },
        "reconnect_recovery": {
            "resumed_runs": len(resumed_ids),
            "resumed_completed": resumed_statuses.get("completed", 0),
            "resumed_unfinished": sum(
                count for status, count in resumed_statuses.items() if status not in {"completed", "failed", "cancelled"}
            ),
        },
        "task_latency_ms": {
            "samples": len(latencies),
            "median": _median(latencies),
            "p95": _percentile(latencies, 0.95),
        },
    }


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


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


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))
    return values[index]


__all__ = ["get_baseline_metrics"]
