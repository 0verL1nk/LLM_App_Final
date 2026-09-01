"""Post-turn enqueue of durable feedback analysis for run-backed research turns."""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.orm.feedback_repository import enqueue_feedback_analysis_task
from ..feedback.analysis import process_feedback_analysis

logger = logging.getLogger(__name__)


def enqueue_turn_feedback_analysis(
    *,
    run_uid: str | None,
    user_uuid: str,
    project_uid: str,
    session_uid: str,
    prompt: str = "",
    turn_result: dict[str, Any],
) -> None:
    """Queue one durable analysis task per completed run-backed turn.

    Steering and mode-switch rules read the durable runtime tables, so the
    only turn-scoped facts carried here are the citation audit fields that
    exist nowhere else in queryable form. Turns without a run (direct API
    calls, continuations) have no durable signal context and are skipped
    rather than guessed.
    """
    if not run_uid or not str(prompt or "").strip():
        return
    try:
        task, created = enqueue_feedback_analysis_task(
            run_uid=str(run_uid),
            user_uuid=user_uuid,
            project_uid=project_uid,
            session_uid=session_uid,
            citation_audit=str(turn_result.get("citation_audit") or ""),
            retrieved_evidence_count=len(
                turn_result.get("retrieved_evidence_items") or []
            ),
            evidence_doc_uids=_evidence_doc_uids(turn_result),
        )
    except Exception:
        logger.exception(
            "Feedback analysis enqueue failed: run_uid=%s project_uid=%s", run_uid, project_uid
        )
        return
    if not created:
        return
    from utils.task_queue import enqueue_background_task

    enqueue_background_task(process_feedback_analysis, str(task["task_uid"]))


def _evidence_doc_uids(turn_result: dict[str, Any]) -> list[str]:
    """Cited document uids bucket findings by the documents a signal involves."""
    doc_uids: set[str] = set()
    for item in turn_result.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        doc_uid = str(item.get("doc_uid") or "").strip()
        if doc_uid:
            doc_uids.add(doc_uid)
    return sorted(doc_uids)


__all__ = ["enqueue_turn_feedback_analysis"]
