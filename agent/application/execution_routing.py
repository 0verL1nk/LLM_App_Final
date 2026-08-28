"""Deterministic, persisted routing for one research Run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionMode = Literal["auto", "react", "plan_execute", "agent_teams"]
ResolvedExecutionMode = Literal["react", "plan_execute", "agent_teams"]

# Structural escalation threshold: at least this many READY (retrievable)
# documents in the project escalates auto runs to the planning profile.
MULTI_DOCUMENT_PLAN_THRESHOLD = 2


@dataclass(frozen=True)
class ExecutionRoute:
    """The server-side mode decision recorded with a Run."""

    requested_mode: ExecutionMode
    resolved_mode: ResolvedExecutionMode
    reason: str


def resolve_execution_route(
    *,
    prompt: str,
    requested_mode: str,
    document_count: int = 0,
) -> ExecutionRoute:
    """Resolve a bounded mode from structural signals only.

    The prompt is accepted for audit context but never parsed: keyword tables
    and length thresholds are pseudo-intelligence (behavior that looks like
    judgment but is string matching) and are deliberately absent. agent_teams
    is never auto-assigned - recursive delegation capability requires explicit
    user selection.
    """
    requested = str(requested_mode or "auto").strip().lower()
    if requested in {"react", "plan_execute", "agent_teams"}:
        return ExecutionRoute(requested, requested, "user_selected")  # type: ignore[arg-type]
    if requested != "auto":
        return ExecutionRoute("auto", "react", "invalid_override_fallback")

    if int(document_count) >= MULTI_DOCUMENT_PLAN_THRESHOLD:
        return ExecutionRoute("auto", "plan_execute", "multi_document_scope")
    return ExecutionRoute("auto", "react", "bounded_direct_request")


__all__ = [
    "MULTI_DOCUMENT_PLAN_THRESHOLD",
    "ExecutionMode",
    "ExecutionRoute",
    "ResolvedExecutionMode",
    "resolve_execution_route",
]
