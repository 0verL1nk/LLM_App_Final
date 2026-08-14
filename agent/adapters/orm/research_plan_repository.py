"""Durable plan snapshots and task-linked step lifecycle transitions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, and_, delete, insert, select, update

from .database import begin_runtime_write, create_engine
from .models import research_plan_steps, research_plans
from .runtime_schema import ensure_runtime_schema

_TERMINAL_STEP_STATUSES = frozenset({"completed", "failed", "cancelled", "blocked"})


class PlanRevisionConflictError(ValueError):
    """Raised when a plan update does not advance the persisted revision."""


def save_plan_snapshot(*, run_uid: str, snapshot: dict[str, Any], db_name: str = "./database.sqlite") -> None:
    """Replace one run's plan snapshot using a durable revision compare-and-set."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            _save_plan_snapshot(connection, run_uid=run_uid, snapshot=snapshot)
    finally:
        engine.dispose()


def link_task_to_plan_step(*, run_uid: str, step_id: str, task_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Attach one durable task to a declared step without inventing a new plan."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            return link_task_to_plan_step_in_transaction(connection, run_uid=run_uid, step_id=step_id, task_uid=task_uid)
    finally:
        engine.dispose()


def link_task_to_plan_step_in_transaction(connection: Connection, *, run_uid: str, step_id: str, task_uid: str) -> bool:
    """Attach a task inside the caller's task-state transaction."""
    updated = connection.execute(
        update(research_plan_steps)
        .where(and_(research_plan_steps.c.run_uid == run_uid, research_plan_steps.c.step_id == step_id, research_plan_steps.c.task_uid.is_(None)))
        .values(task_uid=task_uid, updated_at=_now())
    )
    return updated.rowcount == 1


def transition_linked_plan_step_in_transaction(connection: Connection, *, task_uid: str, status: str) -> None:
    """Reflect an owned task transition in its linked plan step atomically."""
    step_status = {"leased": "in_progress", "running": "in_progress", "completed": "completed", "failed": "failed", "cancelled": "cancelled"}.get(status)
    if step_status is None:
        return
    connection.execute(
        update(research_plan_steps)
        .where(research_plan_steps.c.task_uid == task_uid)
        .values(status=step_status, updated_at=_now())
    )


def task_is_runnable_in_transaction(connection: Connection, *, task_uid: str) -> bool:
    """Allow a linked task only after all declared step dependencies complete."""
    step = connection.execute(select(research_plan_steps).where(research_plan_steps.c.task_uid == task_uid)).first()
    if step is None:
        return True
    data = step._mapping
    dependencies = json.loads(str(data["depends_on_json"]))
    if not dependencies:
        return True
    rows = connection.execute(
        select(research_plan_steps.c.step_id, research_plan_steps.c.status).where(research_plan_steps.c.run_uid == data["run_uid"])
    ).all()
    statuses = {str(row._mapping["step_id"]): str(row._mapping["status"]) for row in rows}
    return all(statuses.get(str(dependency)) == "completed" for dependency in dependencies)


def get_research_plan(*, run_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Return the current plan projection for a durable run."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            plan = connection.execute(select(research_plans).where(research_plans.c.run_uid == run_uid)).first()
            if plan is None:
                return None
            steps = connection.execute(select(research_plan_steps).where(research_plan_steps.c.run_uid == run_uid).order_by(research_plan_steps.c.step_id)).all()
            return {"revision": int(plan._mapping["revision"]), "goal": str(plan._mapping["goal"]), "steps": [_step_from_row(row) for row in steps]}
    finally:
        engine.dispose()


def _save_plan_snapshot(connection: Connection, *, run_uid: str, snapshot: dict[str, Any]) -> None:
    revision = int(snapshot["revision"])
    goal = str(snapshot["goal"]).strip()
    steps = list(snapshot.get("steps") or [])
    existing = connection.execute(select(research_plans.c.revision).where(research_plans.c.run_uid == run_uid)).scalar_one_or_none()
    expected = 0 if existing is None else int(existing) + 1
    if revision != expected:
        raise PlanRevisionConflictError(f"Plan revision conflict: expected {expected}, received {revision}.")
    timestamp = _now()
    if existing is None:
        connection.execute(insert(research_plans).values(run_uid=run_uid, revision=revision, goal=goal, created_at=timestamp, updated_at=timestamp))
    else:
        connection.execute(update(research_plans).where(research_plans.c.run_uid == run_uid).values(revision=revision, goal=goal, updated_at=timestamp))
    prior_tasks = {str(row._mapping["step_id"]): row._mapping["task_uid"] for row in connection.execute(select(research_plan_steps.c.step_id, research_plan_steps.c.task_uid).where(research_plan_steps.c.run_uid == run_uid)).all()}
    connection.execute(delete(research_plan_steps).where(research_plan_steps.c.run_uid == run_uid))
    for step in steps:
        step_id = str(step["id"])
        connection.execute(insert(research_plan_steps).values(run_uid=run_uid, step_id=step_id, title=str(step["title"]), status=str(step.get("status") or "pending"), depends_on_json=json.dumps(step.get("depends_on") or []), lane=str(step.get("lane") or "main"), task_uid=step.get("task_uid") or prior_tasks.get(step_id), created_at=timestamp, updated_at=timestamp))


def _step_from_row(row: Any) -> dict[str, Any]:
    data = row._mapping
    return {"id": str(data["step_id"]), "title": str(data["title"]), "status": str(data["status"]), "depends_on": json.loads(str(data["depends_on_json"])), "lane": str(data["lane"]), "task_uid": data["task_uid"]}


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["PlanRevisionConflictError", "get_research_plan", "link_task_to_plan_step", "link_task_to_plan_step_in_transaction", "save_plan_snapshot", "task_is_runnable_in_transaction", "transition_linked_plan_step_in_transaction"]
