"""Plan middleware for managing execution plans in agent state."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from typing_extensions import NotRequired, TypedDict

from ..adapters.orm.research_plan_repository import PlanRevisionConflictError, save_plan_snapshot
from .types import AgentState


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
        """Initialize the PlanMiddleware."""
        super().__init__()

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
