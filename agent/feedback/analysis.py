"""Deterministic post-turn feedback analysis for the research feedback loop.

The worker re-reads every input from durable runtime tables (runs, steering
inputs), applies the pure rules in ``rules.py``, and records redacted signal
events. Raw prompt/answer text is never persisted here: events carry digests
and short previews only. Safe to invoke from RQ or the local thread queue.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from ..adapters.orm.feedback_repository import (
    claim_feedback_analysis_task,
    complete_feedback_analysis_task,
    get_feedback_run_row,
    get_previous_session_run,
    list_run_steering_inputs,
    record_feedback_event,
)
from .rules import (
    SteeringInputFact,
    evaluate_correction_followup,
    evaluate_evidence_gap,
    evaluate_mode_switch_reask,
    prompt_digest,
    redact_preview,
)

logger = logging.getLogger(__name__)


def process_feedback_analysis(task_uid: str, db_name: str = "./database.sqlite") -> None:
    """Process one durable analysis task; failures mark the task failed, never raise."""
    task = claim_feedback_analysis_task(task_uid=task_uid, db_name=db_name)
    if task is None:
        return
    try:
        for signal in _evaluate_task_signals(task, db_name=db_name):
            record_feedback_event(
                user_uuid=str(task["user_uuid"]),
                project_uid=str(task["project_uid"]),
                session_uid=str(task["session_uid"]),
                run_uid=str(task["run_uid"]),
                signal_type=str(signal["signal_type"]),
                prompt_digest=str(signal["prompt_digest"]),
                trigger_digest=str(signal["trigger_digest"]),
                doc_uid=str(signal["doc_uid"]),
                payload=signal["payload"],
                db_name=db_name,
            )
        complete_feedback_analysis_task(task_uid=task_uid, status="completed", db_name=db_name)
    except Exception as exc:
        complete_feedback_analysis_task(
            task_uid=task_uid, status="failed", error_message=str(exc), db_name=db_name
        )
        logger.exception("Feedback analysis failed: task_uid=%s", task_uid)


def _evaluate_task_signals(task: dict[str, Any], *, db_name: str) -> list[dict[str, Any]]:
    """Apply all three deterministic rules to one completed turn's data."""
    run = get_feedback_run_row(run_uid=str(task["run_uid"]), db_name=db_name)
    if run is None:
        return []
    prompt = str(run.get("prompt") or "")
    digest = prompt_digest(prompt)
    doc_uids = _load_doc_uids(str(task.get("evidence_doc_uids_json") or "[]"))
    doc_bucket = doc_uids[0] if doc_uids else ""

    signals: list[dict[str, Any]] = []
    completed_at = _parse_timestamp(str(task.get("created_at") or ""))
    if completed_at is not None:
        steering_inputs = [
            SteeringInputFact(
                input_uid=str(item.get("input_uid") or ""),
                text=str(item.get("text") or ""),
                created_at=str(item.get("created_at") or ""),
            )
            for item in list_run_steering_inputs(run_uid=str(task["run_uid"]), db_name=db_name)
        ]
        signals.extend(
            _finalize(signal, digest=digest, doc_uids=doc_uids, doc_bucket=doc_bucket)
            for signal in evaluate_correction_followup(
                prompt=prompt,
                steering_inputs=steering_inputs,
                completed_at=completed_at,
            )
        )
    previous = get_previous_session_run(run_uid=str(task["run_uid"]), db_name=db_name)
    if previous is not None:
        mode_signal = evaluate_mode_switch_reask(
            prompt=prompt,
            requested_mode=str(run.get("requested_mode") or ""),
            previous_prompt=str(previous.get("prompt") or ""),
            previous_requested_mode=str(previous.get("requested_mode") or ""),
        )
        if mode_signal is not None:
            signals.append(
                _finalize(mode_signal, digest=digest, doc_uids=doc_uids, doc_bucket=doc_bucket)
            )
    gap_signal = evaluate_evidence_gap(
        citation_audit=str(task.get("citation_audit") or ""),
        retrieved_evidence_count=int(task.get("retrieved_evidence_count") or 0),
    )
    if gap_signal is not None:
        gap_signal["trigger_digest"] = digest
        gap_signal["payload"]["prompt_preview"] = redact_preview(prompt)
        signals.append(_finalize(gap_signal, digest=digest, doc_uids=doc_uids, doc_bucket=doc_bucket))
    return signals


def _finalize(
    signal: dict[str, Any], *, digest: str, doc_uids: list[str], doc_bucket: str
) -> dict[str, Any]:
    """Attach shared provenance fields without ever adding raw full text."""
    payload = dict(signal.get("payload") or {})
    payload.setdefault("doc_uids", doc_uids)
    return {
        "signal_type": signal["signal_type"],
        "trigger_digest": str(signal.get("trigger_digest") or digest),
        "prompt_digest": digest,
        "doc_uid": doc_bucket,
        "payload": payload,
    }


def _load_doc_uids(raw_json: str) -> list[str]:
    try:
        items = json.loads(raw_json)
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    return sorted({str(item) for item in items if str(item)})


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


__all__ = ["process_feedback_analysis"]
