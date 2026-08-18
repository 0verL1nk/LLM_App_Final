"""Revisioned plan tool owned by the Leader Agent.

NOTE: Do NOT add ``from __future__ import annotations`` here. Stringified
annotations break langchain_core's injected-arg detection for the ``runtime:
ToolRuntime`` parameter, so the runtime value would never reach the function.
"""

from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
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


class ReadPlanInput(BaseModel):
    """read_plan takes no model-facing arguments."""


def _update_plan(
    runtime: ToolRuntime,
    revision: int,
    goal: str,
    steps: list[PlanStep],
) -> Command[Any]:
    """Replace the plan only when the supplied revision follows the current one."""
    tool_call_id = str(runtime.tool_call_id or "")
    state = runtime.state if isinstance(runtime.state, dict) else {}
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


def _read_plan(runtime: ToolRuntime) -> str:
    """Read the current revisioned plan snapshot."""
    state = runtime.state if isinstance(runtime.state, dict) else {}
    plan = state.get("plan")
    if not isinstance(plan, dict):
        return "No active plan. Use update_plan only when a plan is useful."
    return str(plan)


update_plan = StructuredTool.from_function(
    name="update_plan",
    description="Replace the plan only when the supplied revision follows the current one.",
    func=_update_plan,
    args_schema=UpdatePlanInput,
    infer_schema=False,
)

read_plan = StructuredTool.from_function(
    name="read_plan",
    description="Read the current revisioned plan snapshot.",
    func=_read_plan,
    args_schema=ReadPlanInput,
    infer_schema=False,
)

PLAN_TOOLS = [update_plan, read_plan]

__all__ = [
    "PLAN_TOOLS",
    "PlanStep",
    "ReadPlanInput",
    "UpdatePlanInput",
    "read_plan",
    "update_plan",
]
