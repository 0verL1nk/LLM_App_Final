"""Writing-draft research artifact routes: scoped creation, revisions, decisions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ValidationError

from agent.adapters.orm.research_artifact_repository import (
    add_research_artifact_revision,
    create_scoped_research_artifact,
    decide_research_artifact_revision,
    get_research_artifact,
    list_research_artifact_revisions,
    list_research_artifacts,
)
from agent.adapters.orm.run_repository import get_run
from agent.adapters.sqlite.project_repository import list_project_sessions
from agent.application.workspace import require_project
from agent.domain.writing import DraftRevision, WritingBrief

router = APIRouter(tags=["writing-artifacts"])


class WritingDraftRequest(BaseModel):
    brief: dict[str, Any]
    revision: dict[str, Any]
    source_run_uid: str = ""


class RevisionRequest(BaseModel):
    revision: dict[str, Any]


class RevisionDecisionRequest(BaseModel):
    decision: str
    note: str = ""


def _validated_contracts(brief: dict[str, Any], revision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enforce the domain writing contracts server-side (422 on violation)."""
    try:
        validated_brief = WritingBrief.model_validate(brief)
        validated_revision = DraftRevision.model_validate(revision)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return validated_brief.model_dump(), validated_revision.model_dump(exclude_none=True)


def _scope_evidence_refs(*, project_uid: str, session_uid: str, user_uuid: str) -> set[str]:
    allowed: set[str] = set()
    for artifact in list_research_artifacts(
        project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid
    ):
        allowed.update(str(ref) for ref in artifact.get("evidence_refs") or [])
    return allowed


def _validated_revision(revision: dict[str, Any], allowed: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Strip out-of-scope evidence refs and surface them as citation gaps."""
    kept_refs: list[str] = []
    dropped: list[str] = []

    def _drop(ref: str) -> None:
        if ref not in dropped:
            dropped.append(ref)

    for ref in revision.get("evidence_refs") or []:
        if str(ref) in allowed:
            kept_refs.append(str(ref))
        else:
            _drop(str(ref))
    spans = []
    for span in revision.get("claim_spans") or []:
        refs = [str(ref) for ref in span.get("evidence_refs") or []]
        for ref in refs:
            if ref not in allowed:
                _drop(ref)
        spans.append({**span, "evidence_refs": [ref for ref in refs if ref in allowed]})
    gaps = [str(gap) for gap in revision.get("citation_gaps") or []]
    for ref in dropped:
        gaps.append(f"证据引用不在当前会话证据范围内：{ref}")
    return {**revision, "evidence_refs": kept_refs, "claim_spans": spans, "citation_gaps": gaps}, dropped


def _owned_artifact(*, artifact_uid: str, user_uuid: str) -> dict[str, Any]:
    artifact = get_research_artifact(artifact_uid=artifact_uid)
    if artifact is None or str(artifact.get("uuid") or "") != user_uuid:
        raise HTTPException(status_code=404, detail="Research artifact not found")
    return artifact


@router.post("/projects/{project_uid}/sessions/{session_uid}/research-artifacts/writing-drafts", status_code=201)
def create_writing_draft(
    project_uid: str,
    session_uid: str,
    payload: WritingDraftRequest,
    user_uuid: str = Header(alias="X-User-Id"),
) -> dict[str, Any]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    sessions = list_project_sessions(project_uid, user_uuid)
    if not any(str(session.get("session_uid")) == session_uid for session in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.source_run_uid and get_run(run_uid=payload.source_run_uid, user_uuid=user_uuid) is None:
        raise HTTPException(status_code=404, detail="Source Run not found")
    allowed = _scope_evidence_refs(project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid)
    revision, dropped = _validated_revision(payload.revision, allowed)
    _brief, revision = _validated_contracts(payload.brief, revision)
    artifact = create_scoped_research_artifact(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        artifact_type="writing_draft",
        content={
            "brief": payload.brief,
            "revision": revision,
            "validation": {"dropped_evidence_refs": dropped},
        },
        evidence_refs=list(revision.get("evidence_refs") or []),
        validity_scope=f"project:{project_uid}/session:{session_uid}",
        source_run_uid=payload.source_run_uid,
    )
    return {"data": artifact}


@router.post("/research-artifacts/{artifact_uid}/revisions", status_code=201)
def propose_artifact_revision(
    artifact_uid: str,
    payload: RevisionRequest,
    user_uuid: str = Header(alias="X-User-Id"),
) -> dict[str, Any]:
    artifact = _owned_artifact(artifact_uid=artifact_uid, user_uuid=user_uuid)
    allowed = _scope_evidence_refs(
        project_uid=str(artifact["project_uid"]), session_uid=str(artifact["session_uid"]), user_uuid=user_uuid
    )
    revision, dropped = _validated_revision(payload.revision, allowed)
    _brief, revision = _validated_contracts({"audience": "读者", "purpose": "修订"}, revision)
    stored = add_research_artifact_revision(
        artifact_uid=artifact_uid,
        content={"revision": revision, "validation": {"dropped_evidence_refs": dropped}},
        evidence_refs=list(revision.get("evidence_refs") or []),
    )
    return {"data": stored}


@router.post("/research-artifacts/{artifact_uid}/revisions/{revision_uid}/decision")
def decide_artifact_revision(
    artifact_uid: str,
    revision_uid: str,
    payload: RevisionDecisionRequest,
    user_uuid: str = Header(alias="X-User-Id"),
) -> dict[str, Any]:
    _owned_artifact(artifact_uid=artifact_uid, user_uuid=user_uuid)
    try:
        revision, changed = decide_research_artifact_revision(
            artifact_uid=artifact_uid,
            revision_uid=revision_uid,
            decision=payload.decision,
            note=payload.note,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"data": {**revision, "changed": changed}}


@router.get("/research-artifacts/{artifact_uid}/revisions")
def list_artifact_revisions(
    artifact_uid: str,
    user_uuid: str = Header(alias="X-User-Id"),
) -> dict[str, Any]:
    _owned_artifact(artifact_uid=artifact_uid, user_uuid=user_uuid)
    return {"data": list_research_artifact_revisions(artifact_uid=artifact_uid)}
