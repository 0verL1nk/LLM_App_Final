"""V2 Run-item lifecycle and payload contracts shared by persistence and the wire.

The event log stays canonical; these contracts are enforced at the persistence
boundary so no unknown item type, status or lifecycle violation becomes durable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .agent_task import RunItemStatus, RunItemType


class RunItemEventType(StrEnum):
    ITEM_CREATED = "item.created"
    ITEM_DELTA = "item.delta"
    ITEM_COMPLETED = "item.completed"
    ITEM_FAILED = "item.failed"
    ITEM_CANCELLED = "item.cancelled"


TERMINAL_ITEM_STATUSES = frozenset(
    {
        RunItemStatus.COMPLETED,
        RunItemStatus.FAILED,
        RunItemStatus.CANCELLED,
    }
)

_DELTA_TERMINAL_ITEM_TYPES = frozenset(
    {RunItemType.ASSISTANT_MESSAGE, RunItemType.REASONING_SUMMARY, RunItemType.PRESENTATION}
)


_EVENT_STATUS_COMPAT: dict[RunItemEventType, frozenset[RunItemStatus]] = {
    RunItemEventType.ITEM_CREATED: frozenset({RunItemStatus.IN_PROGRESS}),
    RunItemEventType.ITEM_DELTA: frozenset({RunItemStatus.IN_PROGRESS}),
    RunItemEventType.ITEM_COMPLETED: frozenset({RunItemStatus.COMPLETED}),
    RunItemEventType.ITEM_FAILED: frozenset({RunItemStatus.FAILED}),
    RunItemEventType.ITEM_CANCELLED: frozenset({RunItemStatus.CANCELLED}),
}

SENSITIVE_ITEM_KEYS = frozenset({
    "api_key", "api-key", "apikey", "authorization", "password", "secret", "token",
    "access_token", "refresh_token", "id_token", "bearer", "credentials", "cookie",
    "set-cookie", "session", "private_key", "client_secret",
})


class RunItemProtocolError(ValueError):
    """Raised before persistence when an item event violates the V2 contract."""


class _ItemPayload(BaseModel):
    """Payload base: known fields are typed, unknown fields survive sanitization."""

    model_config = ConfigDict(extra="allow")


class AssistantMessagePayload(_ItemPayload):
    partId: str = Field(default="", max_length=256)
    text: str | None = Field(default=None, max_length=200_000)
    delta: str | None = Field(default=None, max_length=200_000)


class ReasoningSummaryPayload(_ItemPayload):
    partId: str = Field(default="", max_length=256)
    text: str | None = Field(default=None, max_length=200_000)
    delta: str | None = Field(default=None, max_length=200_000)


class PlanStepPayload(_ItemPayload):
    id: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=2000)
    status: str = Field(default="pending", max_length=32)
    depends_on: list[str] = Field(default_factory=list)
    lane: str = Field(default="main", max_length=80)
    task_uid: str | None = Field(default=None, max_length=128)


class PlanSnapshotPayload(_ItemPayload):
    goal: str | None = Field(default=None, max_length=4000)
    revision: int | None = Field(default=None, ge=0)
    steps: list[PlanStepPayload] = Field(default_factory=list, max_length=64)


class PlanItemPayload(_ItemPayload):
    summary: str | None = Field(default=None, max_length=4000)
    toolName: str | None = Field(default=None, max_length=128)
    durationMs: float | None = Field(default=None, ge=0)
    plan: PlanSnapshotPayload | None = None


class ToolCallPayload(_ItemPayload):
    summary: str | None = Field(default=None, max_length=4000)
    toolName: str | None = Field(default=None, max_length=128)
    durationMs: float | None = Field(default=None, ge=0)


class AgentTaskPayload(_ItemPayload):
    agent: str | None = Field(default=None, max_length=128)
    task: str | None = Field(default=None, max_length=4000)
    summary: str | None = Field(default=None, max_length=4000)


class HumanRequestPayload(_ItemPayload):
    inputId: str | None = Field(default=None, max_length=128)
    text: str | None = Field(default=None, max_length=200_000)
    state: str | None = Field(default=None, max_length=32)


class PresentationPayload(_ItemPayload):
    partId: str = Field(default="", max_length=256)
    presentation: str | None = Field(default=None, max_length=32)
    envelope: dict[str, Any] | None = None
    surface: dict[str, Any] | None = None
    message: str | None = Field(default=None, max_length=2000)


class FailurePayload(_ItemPayload):
    message: str = Field(default="", max_length=4000)
    category: str | None = Field(default=None, max_length=64)


ITEM_PAYLOAD_MODELS: dict[RunItemType, type[_ItemPayload]] = {
    RunItemType.ASSISTANT_MESSAGE: AssistantMessagePayload,
    RunItemType.REASONING_SUMMARY: ReasoningSummaryPayload,
    RunItemType.PLAN: PlanItemPayload,
    RunItemType.TOOL_CALL: ToolCallPayload,
    RunItemType.AGENT_TASK: AgentTaskPayload,
    RunItemType.HUMAN_REQUEST: HumanRequestPayload,
    RunItemType.PRESENTATION: PresentationPayload,
    RunItemType.FAILURE: FailurePayload,
}


def is_terminal_item_status(status: str) -> bool:
    """Return whether ``status`` is a terminal V2 item state."""
    try:
        return RunItemStatus(status) in TERMINAL_ITEM_STATUSES
    except ValueError:
        return False


def sanitize_item_payload(value: Any) -> Any:
    """Drop credential-shaped keys recursively before an item becomes durable."""
    if isinstance(value, dict):
        return {
            str(key): sanitize_item_payload(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_ITEM_KEYS
        }
    if isinstance(value, list):
        return [sanitize_item_payload(item) for item in value]
    return value


def validate_item_event(
    *,
    item_uid: str,
    item_type: str,
    status: str,
    event_type: str,
    payload: dict[str, Any],
    existing_status: str | None = None,
) -> dict[str, Any]:
    """Validate and sanitize one item event; raise before anything is persisted.

    ``existing_status`` is the item projection's current status (``None`` when the
    item id is unknown).  A delta may materialize a not-yet-created item and a
    terminal may close an item whose creation was never observed, but an item id
    admits at most one creation event and exactly one terminal event.
    """
    try:
        typed_item_type = RunItemType(str(item_type).strip())
    except ValueError as exc:
        raise RunItemProtocolError(f"Unknown run item type: {item_type!r}") from exc
    try:
        typed_status = RunItemStatus(str(status).strip())
    except ValueError as exc:
        raise RunItemProtocolError(f"Unknown run item status: {status!r}") from exc
    try:
        typed_event = RunItemEventType(str(event_type).strip())
    except ValueError as exc:
        raise RunItemProtocolError(f"Unknown run item event type: {event_type!r}") from exc
    delta_completes = (
        typed_event is RunItemEventType.ITEM_DELTA
        and typed_status is RunItemStatus.COMPLETED
        and typed_item_type in _DELTA_TERMINAL_ITEM_TYPES
    )
    if typed_status not in _EVENT_STATUS_COMPAT[typed_event] and not delta_completes:
        raise RunItemProtocolError(f"Item event {typed_event.value} cannot carry status {typed_status.value}")
    if existing_status is not None:
        if is_terminal_item_status(existing_status):
            raise RunItemProtocolError(
                f"Item {item_uid} is already terminal ({existing_status}); no further item events are allowed"
            )
        if typed_event is RunItemEventType.ITEM_CREATED:
            raise RunItemProtocolError(f"Item {item_uid} already exists; a second item.created is not allowed")
    sanitized = sanitize_item_payload(payload)
    try:
        validated = ITEM_PAYLOAD_MODELS[typed_item_type].model_validate(sanitized)
    except ValidationError as exc:
        raise RunItemProtocolError(f"Item {item_uid} payload does not match the {typed_item_type.value} contract") from exc
    return validated.model_dump(exclude_none=True)


def merge_item_payload(
    existing_payload: dict[str, Any],
    *,
    item_type: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fold one applied item event into the item's latest-complete projection."""
    if item_type in {"assistant_message", "reasoning_summary"} and event_type == "item.delta":
        return {**existing_payload, **payload, "text": str(existing_payload.get("text") or "") + str(payload.get("delta") or "")}
    if item_type == "presentation" and event_type == "item.delta":
        envelopes = list(existing_payload.get("envelopes") or [])
        if isinstance(payload.get("envelope"), dict):
            envelopes.append(payload["envelope"])
        return {**existing_payload, **payload, "envelopes": envelopes}
    return {**existing_payload, **payload}


__all__ = [
    "AgentTaskPayload",
    "AssistantMessagePayload",
    "FailurePayload",
    "HumanRequestPayload",
    "ITEM_PAYLOAD_MODELS",
    "PlanItemPayload",
    "PlanSnapshotPayload",
    "PlanStepPayload",
    "PresentationPayload",
    "ReasoningSummaryPayload",
    "RunItemEventType",
    "RunItemProtocolError",
    "SENSITIVE_ITEM_KEYS",
    "TERMINAL_ITEM_STATUSES",
    "ToolCallPayload",
    "is_terminal_item_status",
    "merge_item_payload",
    "sanitize_item_payload",
    "validate_item_event",
]
