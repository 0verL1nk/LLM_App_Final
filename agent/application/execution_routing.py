"""Deterministic, persisted routing for one research Run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionMode = Literal["auto", "react", "plan_execute", "agent_teams"]
ResolvedExecutionMode = Literal["react", "plan_execute", "agent_teams"]


@dataclass(frozen=True)
class ExecutionRoute:
    """The server-side mode decision recorded with a Run."""

    requested_mode: ExecutionMode
    resolved_mode: ResolvedExecutionMode
    reason: str


def resolve_execution_route(*, prompt: str, requested_mode: str) -> ExecutionRoute:
    """Resolve a bounded mode without an LLM preflight or legacy interceptor."""
    requested = str(requested_mode or "auto").strip().lower()
    if requested in {"react", "plan_execute", "agent_teams"}:
        return ExecutionRoute(requested, requested, "user_selected")  # type: ignore[arg-type]
    if requested != "auto":
        return ExecutionRoute("auto", "react", "invalid_override_fallback")

    text = " ".join(str(prompt or "").lower().split())
    team_markers = ("对比", "比较", "审查", "review", "compare", "多个论文", "多篇", "分别")
    plan_markers = ("步骤", "计划", "方案", "分析", "调研", "研究", "实现", "设计", "plan")
    if sum(marker in text for marker in team_markers) >= 2 or ("对比" in text and "证据" in text):
        return ExecutionRoute("auto", "agent_teams", "independent_comparison_or_review")
    if any(marker in text for marker in plan_markers) or len(text) >= 180:
        return ExecutionRoute("auto", "plan_execute", "multi_step_or_long_request")
    return ExecutionRoute("auto", "react", "bounded_direct_request")


__all__ = ["ExecutionMode", "ExecutionRoute", "ResolvedExecutionMode", "resolve_execution_route"]
