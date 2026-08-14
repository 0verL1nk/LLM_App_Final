"""Revisioned plan tool owned by the Leader Agent."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field, model_validator


class PlanStep(BaseModel):
    """One explicit plan step with dependency and optional task linkage."""

    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    status: Literal["pending", "in_progress", "completed", "blocked", "failed"] = "pending"
    depends_on: list[str] = Field(default_factory=list)
    lane: str = Field(default="main", min_length=1, max_length=80)
    task_uid: str | None = None


class UpdatePlanInput(BaseModel):
    """Complete replacement snapshot guarded by the caller's plan revision."""

    revision: int = Field(ge=0)
    goal: str = Field(min_length=1, max_length=1000)
    steps: list[PlanStep] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "UpdatePlanInput":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan step IDs must be unique")
        known = set(ids)
        for step in self.steps:
            if step.id in step.depends_on or any(dep not in known for dep in step.depends_on):
                raise ValueError("Plan dependencies must reference a different declared step")
        return self


@tool("update_plan", args_schema=UpdatePlanInput)
def update_plan(
    revision: int,
    goal: str,
    steps: list[PlanStep],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict[str, Any], InjectedState],
) -> Command[Any]:
    """Replace the plan only when the supplied revision follows the current one."""
    current = state.get("plan") if isinstance(state.get("plan"), dict) else None
    expected = 0 if current is None else int(current.get("revision", -1)) + 1
    if revision != expected:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Plan revision conflict: expected {expected}, received {revision}.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    snapshot = {
        "revision": revision,
        "goal": goal.strip(),
        "steps": [step.model_dump(exclude_none=True) for step in steps],
    }
    return Command(
        update={
            "plan": snapshot,
            "messages": [ToolMessage(f"Plan revision {revision} saved.", tool_call_id=tool_call_id)],
        }
    )


@tool("read_plan")
def read_plan(state: Annotated[dict[str, Any], InjectedState]) -> str:
    """Read the current revisioned plan snapshot."""
    plan = state.get("plan")
    if not isinstance(plan, dict):
        return "No active plan. Use update_plan only when a plan is useful."
    return str(plan)


PLAN_TOOLS = [update_plan, read_plan]

__all__ = ["PLAN_TOOLS", "PlanStep", "UpdatePlanInput", "read_plan", "update_plan"]
