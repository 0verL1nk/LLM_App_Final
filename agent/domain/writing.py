"""Contracts for evidence-backed writing briefs, revisions and claim spans."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ReviewFindingKind(StrEnum):
    """Locatable review categories an editing or review pass must choose from."""

    OVER_CLAIM = "over_claim"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    METHOD_RESULT_CONFUSION = "method_result_confusion"
    MISSED_COUNTEREXAMPLE = "missed_counterexample"
    TERMINOLOGY_INCONSISTENCY = "terminology_inconsistency"
    CITATION_GAP = "citation_gap"


class ReviewFinding(BaseModel):
    """One review note that points at a section, paragraph or claim id."""

    kind: ReviewFindingKind
    location: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=2000)


class ClaimSpan(BaseModel):
    """A draft text span mapped back to the evidence that supports its claim."""

    claim_id: str = Field(min_length=1, max_length=256)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=1000)


class WritingBrief(BaseModel):
    """Audience, purpose and constraints the writing agent converts into a draft."""

    audience: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1000)
    target_section: str = Field(default="", max_length=500)
    claim_budget: int = Field(default=0, ge=0)
    style_constraints: list[str] = Field(default_factory=list)


class DraftRevision(BaseModel):
    """One immutable draft proposal; accepting it never overwrites prior revisions."""

    section: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=200_000)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    claim_spans: list[ClaimSpan] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=4000)
    unsupported_claims: list[str] = Field(default_factory=list)
    citation_gaps: list[str] = Field(default_factory=list)
    review_findings: list[ReviewFinding] = Field(default_factory=list)
    based_on_revision: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def _spans_stay_inside_the_revision(self) -> DraftRevision:
        length = len(self.text)
        seen_ids: set[str] = set()
        for span in self.claim_spans:
            if span.start >= span.end or span.end > length:
                raise ValueError(f"Claim span {span.claim_id!r} lies outside the revision text")
            if span.claim_id in seen_ids:
                raise ValueError(f"Claim span {span.claim_id!r} declared twice")
            seen_ids.add(span.claim_id)
            unknown = sorted(set(span.evidence_refs) - set(self.evidence_refs))
            if unknown:
                raise ValueError(f"Claim span {span.claim_id!r} cites evidence absent from the revision: {unknown}")
        dangling_spans = seen_ids - set(self.claim_ids)
        if dangling_spans:
            raise ValueError(f"Claim spans reference unknown claim ids: {sorted(dangling_spans)}")
        return self


__all__ = [
    "ClaimSpan",
    "DraftRevision",
    "ReviewFinding",
    "ReviewFindingKind",
    "WritingBrief",
]
