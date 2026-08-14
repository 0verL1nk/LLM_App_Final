"""Generic durable task contracts for all Agent runtime work."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class AgentTaskStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING_CHILDREN = "waiting_children"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AgentTaskKind(StrEnum):
    """Built-in kinds; persisted tasks may also use registered extension kinds."""

    LEADER = "leader"
    SUBAGENT = "subagent"
    TOOL = "tool"
    CONTINUATION = "continuation"


_TASK_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def normalize_task_kind(kind: AgentTaskKind | str) -> str:
    """Validate an open task-kind key without restricting registered extensions."""
    normalized = str(kind).strip().lower()
    if not _TASK_KIND_PATTERN.fullmatch(normalized):
        raise ValueError("Task kind must be a lowercase identifier up to 64 characters")
    return normalized


class AgentTaskAttemptStatus(StrEnum):
    LEASED = "leased"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RunItemType(StrEnum):
    ASSISTANT_MESSAGE = "assistant_message"
    REASONING_SUMMARY = "reasoning_summary"
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    AGENT_TASK = "agent_task"
    HUMAN_REQUEST = "human_request"
    PRESENTATION = "presentation"
    FAILURE = "failure"


class RunItemStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_TASK_STATUSES = frozenset(
    {
        AgentTaskStatus.COMPLETED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.CANCELLED,
        AgentTaskStatus.EXPIRED,
    }
)


class AgentTaskInput(TypedDict, total=False):
    objective: str
    capability_ids: list[str]
    depends_on: list[str]
    coordination_mode: str
    payload: dict[str, Any]


class AgentTaskResult(TypedDict, total=False):
    summary: str
    evidence_refs: list[str]
    claims: list[dict[str, Any]]
    limitations: list[str]
    open_questions: list[str]


class EvidenceReference(BaseModel):
    """One evidence coordinate that was retrieved from the task's authorized scope."""

    chunk_id: str = Field(min_length=1, max_length=256)
    doc_uid: str = Field(min_length=1, max_length=256)
    page_no: int | None = Field(default=None, ge=1)
    offset_start: int | None = Field(default=None, ge=0)
    offset_end: int | None = Field(default=None, ge=0)


class AtomicClaim(BaseModel):
    """A bounded research assertion that may cite one or more packet references."""

    statement: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list)
    limitation: str = Field(default="", max_length=1000)


class EvidencePacket(BaseModel):
    """Sanitized child output eligible for a parent continuation."""

    summary: str = Field(min_length=1, max_length=6000)
    evidence_refs: list[str] = Field(default_factory=list)
    claims: list[AtomicClaim] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


def is_terminal_task_status(status: str) -> bool:
    """Return whether ``status`` represents a terminal generic task state."""
    try:
        return AgentTaskStatus(status) in TERMINAL_TASK_STATUSES
    except ValueError:
        return False


__all__ = [
    "AgentTaskAttemptStatus",
    "AgentTaskInput",
    "AgentTaskKind",
    "AgentTaskResult",
    "AgentTaskStatus",
    "AtomicClaim",
    "EvidenceReference",
    "EvidencePacket",
    "RunItemStatus",
    "RunItemType",
    "TERMINAL_TASK_STATUSES",
    "is_terminal_task_status",
    "normalize_task_kind",
]
