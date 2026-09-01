"""HTTP contract for the research feedback loop: findings export and click telemetry."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agent.adapters.orm.feedback_repository import record_evidence_click
from agent.application.feedback_findings import (
    build_feedback_case_draft,
    list_feedback_findings,
)

from .dependencies import current_user_id

UserId = Annotated[str, Depends(current_user_id)]

feedback_findings_router = APIRouter(prefix="/evals/feedback-findings", tags=["feedback"])
evidence_click_router = APIRouter(prefix="/runs", tags=["feedback"])


class EvidenceClickCreate(BaseModel):
    """One user interaction with a cited evidence reference."""

    evidence_ref: str = Field(min_length=1, max_length=256)
    item_uid: str = Field(default="", max_length=128)


@feedback_findings_router.get("")
def get_feedback_findings(project_uid: str | None = None) -> dict[str, Any]:
    """List recurring signal findings for operator review (dev evals page)."""
    return {"data": list_feedback_findings(project_uid=project_uid)}


@feedback_findings_router.post("/{finding_id}/export-case")
def export_feedback_case(finding_id: str) -> dict[str, Any]:
    """Return a JSONL case draft with production provenance; fixtures stay untouched."""
    try:
        draft = build_feedback_case_draft(finding_id=finding_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"data": draft}


@evidence_click_router.post(
    "/{run_uid}/evidence-clicks", status_code=status.HTTP_202_ACCEPTED
)
def create_evidence_click(
    run_uid: str, payload: EvidenceClickCreate, user_uuid: UserId
) -> dict[str, Any]:
    """Record that the user opened one cited evidence reference of a run."""
    try:
        click_id = record_evidence_click(
            run_uid=run_uid,
            user_uuid=user_uuid,
            evidence_ref=payload.evidence_ref,
            item_uid=payload.item_uid,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": {"click_id": click_id, "recorded": True}}
