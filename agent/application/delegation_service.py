"""Application use case for submitting durable Leader delegation."""

from __future__ import annotations

from typing import Any

from ..adapters.orm.research_plan_repository import link_task_to_plan_step
from ..adapters.orm.run_repository import append_run_item_event
from ..adapters.orm.task_dispatch_repository import create_agent_task
from ..domain.agent_task import AgentTaskKind


def submit_delegated_agent_task(
    *,
    run_uid: str,
    tool_call_id: str,
    parent_task_uid: str | None = None,
    role: str,
    description: str,
    mode: str = "join",
    plan_step_id: str | None = None,
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Persist one bounded child task and its V2 item projection."""
    normalized_role = role.strip()
    normalized_description = description.strip()
    normalized_parent_task_uid = (parent_task_uid or "").strip()
    if not normalized_role or not normalized_description:
        raise ValueError("Delegated task role and description are required")
    if mode != "join":
        raise ValueError("Only join delegation is currently supported")
    task, created = create_agent_task(
        run_uid=run_uid,
        parent_task_uid=normalized_parent_task_uid or None,
        kind=AgentTaskKind.SUBAGENT,
        agent_role=normalized_role,
        idempotency_key=f"leader-tool:{tool_call_id}",
        input_payload={
            "objective": normalized_description,
            "coordination_mode": mode,
            "tool_call_id": tool_call_id,
        },
        db_name=db_name,
    )
    append_run_item_event(
        run_uid=run_uid,
        item_uid=f"item_agent_task_{task['task_uid']}",
        item_type="agent_task",
        task_uid=str(task["task_uid"]),
        status="in_progress",
        event_type="item.created",
        payload={"agent": normalized_role, "task": normalized_description, "summary": "已加入任务队列"},
        db_name=db_name,
    )
    if created and plan_step_id:
        if not link_task_to_plan_step(
            run_uid=run_uid,
            step_id=plan_step_id,
            task_uid=str(task["task_uid"]),
            db_name=db_name,
        ):
            raise ValueError("Plan step is unavailable or already linked to another task")
    return task, created


__all__ = ["submit_delegated_agent_task"]
