"""Leader delegation tool backed by generic durable AgentTask persistence.

NOTE: Do NOT add ``from __future__ import annotations`` here. Stringified
annotations break langchain_core's injected-arg detection for the ``runtime:
ToolRuntime`` parameter, so the runtime value would never reach the function.
"""

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
            "Delegate research work to role subagents when a task needs independent "
            "evidence gathering (per-document analysis, multi-source synthesis) or an "
            "independent review pass. When subtasks are independent, emit multiple "
            "delegate_task calls in the SAME turn so they run concurrently; the runtime "
            "joins their results asynchronously. For comparison or adoption-decision "
            "tasks, the same-turn fan-out MUST include one reviewer delegation to "
            "verify the collected evidence - researcher-only fan-outs are incomplete. "
            "Do not delegate recursively and do not "
            "delegate trivial single-lookup work.\n\nAvailable roles:\n" + available
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
