"""Plan middleware for managing execution plans in agent state."""

import os
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from typing_extensions import NotRequired, TypedDict

from ..adapters.orm.research_plan_repository import PlanRevisionConflictError, save_plan_snapshot
from ..tools.plan_tools import PLAN_TOOLS
from .system_message import append_system_instruction
from .types import AgentState

# Progressive hint: when retrieval has started but no plan exists, nudge once
# via the single provider-facing system message (never by mutating tool
# results - those carry the JSON evidence payloads the turn engine parses).
# Env: AGENT_PLAN_NUDGE_ENABLED=0 to disable.
PLAN_NUDGE_MARKER = "[plan-nudge]"
PLAN_NUDGE_INSTRUCTION = (
    f"{PLAN_NUDGE_MARKER} [系统提示] 检索已开始但尚无执行计划:若本任务涉及多篇文档或多个"
    "子目标,请立即调用 update_plan 建立带步骤与状态的计划再继续,并在完成每个步骤后回写其"
    "状态;简单单点查询可忽略本提示。"
)


def _plan_nudge_enabled() -> bool:
    return os.getenv("AGENT_PLAN_NUDGE_ENABLED", "1").strip().lower() not in {"0", "false", "off"}


def _has_search_document_call(messages: list[Any]) -> bool:
    return any(
        str(call.get("name") or "") == "search_document"
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
    )


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

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """Inject the plan nudge into the system message once retrieval runs planless."""
        if not _plan_nudge_enabled():
            return handler(request)
        state = request.state if isinstance(request.state, dict) else {}
        if state.get("plan"):
            return handler(request)
        messages = state.get("messages") or []
        if not _has_search_document_call(messages):
            return handler(request)
        system_message = append_system_instruction(
            request.system_message, PLAN_NUDGE_INSTRUCTION
        )
        return handler(request.override(system_message=system_message))

    def wrap_tool_call(self, request: ToolCallRequest, handler: Any) -> Any:
        """Persist successful ``update_plan`` snapshots for durable worker runs."""
        result = handler(request)
        if str(request.tool_call.get("name") or "") != "update_plan":
            return result
        update = getattr(result, "update", None)
        snapshot = update.get("plan") if isinstance(update, dict) else None
        configurable = request.runtime.config.get("configurable", {})
        run_uid = str(configurable.get("run_uid") or "").strip()
        if not run_uid or not isinstance(snapshot, dict):
            return result
        try:
            save_plan_snapshot(
                run_uid=run_uid,
                snapshot=snapshot,
                db_name=str(configurable.get("task_db_name") or "./database.sqlite"),
            )
        except PlanRevisionConflictError as exc:
            return ToolMessage(str(exc), tool_call_id=request.tool_call["id"], status="error")
        return result


# Create singleton instance
plan_middleware = PlanMiddleware()

__all__ = ["plan_middleware", "ExtendedPlanningState"]
