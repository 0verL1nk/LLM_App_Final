"""Plan middleware for managing execution plans in agent state."""

import os
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from typing_extensions import NotRequired, TypedDict

from ..adapters.orm.research_plan_repository import PlanRevisionConflictError, save_plan_snapshot
from ..tools.plan_tools import PLAN_TOOLS
from .types import AgentState

# Progressive hint: when retrieval has started but no plan exists, nudge once
# from inside the tool result (the model's attention hotspot) instead of
# relying on system-prompt prose. Env: AGENT_PLAN_NUDGE_ENABLED=0 to disable.
PLAN_NUDGE_MARKER = "[plan-nudge]"
PLAN_NUDGE_INSTRUCTION = (
    f"{PLAN_NUDGE_MARKER} [系统提示] 检索已开始但尚无执行计划:若本任务涉及多篇文档或多个"
    "子目标,请立即调用 update_plan 建立带步骤与状态的计划再继续;简单单点查询可忽略本提示。"
)


def _plan_nudge_enabled() -> bool:
    return os.getenv("AGENT_PLAN_NUDGE_ENABLED", "1").strip().lower() not in {"0", "false", "off"}


class PlanStateExtension(TypedDict):
    """State owned by the revisioned plan capability."""

    plan: NotRequired[dict[str, Any] | None]
    """Current revisioned execution plan."""


class ExtendedPlanningState(AgentState, PlanStateExtension):
    """Agent state extended with one revisioned plan snapshot."""

    pass


class PlanMiddleware(AgentMiddleware[ExtendedPlanningState, Any, Any]):
    """Middleware that extends PlanningState to support plan management.

    This middleware adds a 'plan' field to the agent state, allowing
    plan_tools to persist plan data across agent invocations.
    """

    state_schema = ExtendedPlanningState

    def __init__(self) -> None:
        """Initialize the PlanMiddleware.

        Plan tools are provided by the middleware (not as top-level agent tools)
        so the agent runtime injects ToolRuntime state and tool_call_id — the same
        execution path as DurableDelegationMiddleware and the official TodoListMiddleware.
        """
        super().__init__()
        self.tools = list(PLAN_TOOLS)

    def wrap_tool_call(self, request: ToolCallRequest, handler: Any) -> Any:
        """Persist successful ``update_plan`` snapshots for durable worker runs."""
        result = handler(request)
        tool_name = str(request.tool_call.get("name") or "")
        if tool_name == "update_plan":
            update = getattr(result, "update", None)
            snapshot = update.get("plan") if isinstance(update, dict) else None
            configurable = request.runtime.config.get("configurable", {})
            run_uid = str(configurable.get("run_uid") or "").strip()
            if run_uid and isinstance(snapshot, dict):
                try:
                    save_plan_snapshot(
                        run_uid=run_uid,
                        snapshot=snapshot,
                        db_name=str(configurable.get("task_db_name") or "./database.sqlite"),
                    )
                except PlanRevisionConflictError as exc:
                    return ToolMessage(str(exc), tool_call_id=request.tool_call["id"], status="error")
            return result
        if tool_name == "search_document" and _plan_nudge_enabled():
            return self._maybe_nudge_plan(request, result)
        return result

    @staticmethod
    def _maybe_nudge_plan(request: ToolCallRequest, result: Any) -> Any:
        state = request.runtime.state if isinstance(request.runtime.state, dict) else {}
        if state.get("plan"):
            return result
        messages = state.get("messages") or []
        already_nudged = any(
            PLAN_NUDGE_MARKER in str(getattr(message, "content", "") or "")
            for message in messages
        )
        if already_nudged or not isinstance(result, ToolMessage):
            return result
        return ToolMessage(
            content=str(result.content) + "\n\n" + PLAN_NUDGE_INSTRUCTION,
            tool_call_id=result.tool_call_id,
            name=getattr(result, "name", None),
            status=getattr(result, "status", "success"),
        )


# Create singleton instance
plan_middleware = PlanMiddleware()

__all__ = ["plan_middleware", "ExtendedPlanningState"]
