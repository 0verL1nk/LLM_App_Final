"""Leader delegation tool backed by generic durable AgentTask persistence."""

from __future__ import annotations

import json

from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, Field

from ..application.delegation_service import submit_delegated_agent_task
from ..subagent.loader import SubAgentDefinition


class DelegateTaskInput(BaseModel):
    """Public contract for bounded, first-level research delegation."""

    role: str = Field(description="Configured research role to execute the task.")
    description: str = Field(min_length=1, description="Concrete research objective for this task.")
    mode: str = Field(default="join", description="Coordination mode; only join is currently supported.")
    plan_step_id: str | None = Field(default=None, description="Optional existing plan step to execute.")


class DurableDelegationMiddleware(AgentMiddleware):
    """Expose ``delegate_task`` without executing a child in the Leader process."""

    def __init__(self, definitions: list[SubAgentDefinition]) -> None:
        super().__init__()
        self._roles = {definition.name for definition in definitions}
        available = "\n".join(
            f"- {definition.name}: {definition.description}" for definition in definitions
        )
        self.system_prompt = (
            "Use `delegate_task` only when a distinct evidence task is useful. "
            "It creates durable work and returns its stable task UID; it does not run "
            "a child synchronously. Do not delegate recursively.\n\nAvailable roles:\n" + available
        )
        self.tools = [self._build_tool()]

    def _build_tool(self) -> StructuredTool:
        roles = self._roles

        def delegate_task(
            role: str,
            description: str,
            runtime: ToolRuntime,
            mode: str = "join",
            plan_step_id: str | None = None,
        ) -> str:
            normalized_role = role.strip()
            if normalized_role not in roles:
                return json.dumps({"error": "unknown_role", "available_roles": sorted(roles)}, ensure_ascii=False)
            if mode != "join":
                return json.dumps({"error": "unsupported_mode", "supported_modes": ["join"]}, ensure_ascii=False)
            if not runtime.tool_call_id:
                raise ValueError("Delegation requires a tool-call runtime")
            run_uid = str(runtime.config.get("configurable", {}).get("run_uid") or "").strip()
            parent_task_uid = str(runtime.config.get("configurable", {}).get("task_uid") or "").strip()
            if not run_uid or not parent_task_uid:
                return json.dumps({"error": "durable_run_required"}, ensure_ascii=False)
            db_name = str(runtime.config.get("configurable", {}).get("task_db_name") or "./database.sqlite")
            task, created = submit_delegated_agent_task(
                run_uid=run_uid,
                tool_call_id=runtime.tool_call_id,
                parent_task_uid=parent_task_uid,
                role=normalized_role,
                description=description,
                mode=mode,
                plan_step_id=plan_step_id,
                db_name=db_name,
            )
            if created:
                from ..application.task_delivery import dispatch_task

                dispatch_task(task_uid=str(task["task_uid"]))
            return json.dumps({"task_uid": task["task_uid"], "status": task["status"], "created": created}, ensure_ascii=False)

        return StructuredTool.from_function(
            name="delegate_task",
            func=delegate_task,
            description="Create one durable, first-level research task and return its task_uid.",
            infer_schema=False,
            args_schema=DelegateTaskInput,
        )


__all__ = ["DurableDelegationMiddleware"]
