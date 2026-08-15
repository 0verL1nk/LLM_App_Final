"""Generic durable task contracts for all Agent runtime work."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field, model_validator


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


def is_terminal_task_status(status: str) -> bool:
    """Return whether ``status`` represents a terminal generic task state."""
    try:
        return AgentTaskStatus(status) in TERMINAL_TASK_STATUSES
    except ValueError:
        return False



class ClaimType(StrEnum):
    """Kinds of atomic claims a research deliverable may assert."""

    PAPER_FACT = "paper_fact"
    HYPOTHESIS = "hypothesis"
    CROSS_PAPER_SYNTHESIS = "cross_paper_synthesis"


class EvidenceReference(BaseModel):
    """One citable location: local chunk coordinates or a web source."""

    chunk_id: str = ""
    doc_uid: str = ""
    page_no: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None
    bbox: list[float] | None = None
    source_url: str = ""

    @model_validator(mode="after")
    def _bbox_is_four_normalized_numbers(self) -> "EvidenceReference":
        if self.bbox is None:
            self.bbox = []
        if self.bbox and len(self.bbox) != 4:
            raise ValueError("bbox must contain exactly four normalized coordinates")
        return self


class AtomicClaim(BaseModel):
    """One falsifiable statement plus the evidence that may support it."""

    statement: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.PAPER_FACT
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _paper_facts_require_evidence(self) -> "AtomicClaim":
        if self.claim_type is ClaimType.PAPER_FACT and not self.evidence_refs:
            raise ValueError("paper_fact claims must cite at least one evidence reference")
        return self


class PacketLimitation(BaseModel):
    """A bounded limitation, conflict or caveat attached to a packet."""

    kind: str = "general"
    statement: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    """An unresolved question with the next action that would resolve it."""

    question: str = Field(min_length=1)
    suggested_action: str = ""


class EvidencePacket(BaseModel):
    """Scope-validated research deliverable: claims, evidence, doubts."""

    summary: str = Field(min_length=1)
    research_question: str = ""
    evidence: list[EvidenceReference] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    claims: list[AtomicClaim] = Field(default_factory=list)
    limitations: list[str | PacketLimitation] = Field(default_factory=list)
    open_questions: list[str | OpenQuestion] = Field(default_factory=list)
    confidence: float | None = Field(default=0.5, ge=0.0, le=1.0)
    metrics: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _missing_confidence_defaults_to_half(self) -> "EvidencePacket":
        if self.confidence is None:
            self.confidence = 0.5
        return self


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
    "AtomicClaim",
    "ClaimType",
    "EvidencePacket",
    "EvidenceReference",
    "OpenQuestion",
    "PacketLimitation",
]
