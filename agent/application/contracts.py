from collections.abc import Callable
from typing import Any, TypedDict

from typing_extensions import NotRequired

from ..domain.human_request import HumanRequest
from ..domain.trace import TraceEvent

EventCallback = Callable[[TraceEvent], None]
SearchDocumentFn = Callable[[str], str]


class EmptyModelOutputError(RuntimeError):
    """The provider returned neither assistant text nor a tool call."""


class TurnCoreResult(TypedDict):
    answer: str
    policy_decision: dict[str, Any]
    trace_payload: list[TraceEvent]
    evidence_items: list[dict[str, Any]]
    retrieved_evidence_items: NotRequired[list[dict[str, Any]]]
    mindmap_data: dict[str, Any] | None
    a2ui_surface: NotRequired[dict[str, Any] | None]
    a2ui_surfaces: NotRequired[list[dict[str, Any]]]
    response_parts: NotRequired[list[dict[str, str]]]
    method_compare_data: dict[str, Any] | None
    run_latency_ms: float
    phase_path: str
    used_document_rag: bool
    ask_human_requests: list[HumanRequest]
    leader_tool_names: list[str]
    output_messages: NotRequired[list[Any]]
    plan: NotRequired[dict[str, Any] | None]
    runtime_state: NotRequired[dict[str, Any] | None]
    context_snapshot: NotRequired[dict[str, Any]]
