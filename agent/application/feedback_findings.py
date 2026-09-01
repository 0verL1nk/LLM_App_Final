"""Operator-facing feedback findings and eval case-draft generation.

Findings are query-time aggregations (no second table). Export produces a
JSONL case draft only: merging the draft into a fixture stays an explicit
operator action, per the no-automatic-fixture-writes contract.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..adapters.orm.feedback_repository import (
    aggregate_feedback_findings,
    find_finding_by_id,
    get_feedback_run_row,
    latest_event_for_finding,
)
from ..feedback.rules import (
    SIGNAL_CORRECTION_FOLLOWUP,
    SIGNAL_EVIDENCE_GAP,
    SIGNAL_MODE_SWITCH_REASK,
)

# Provenance marker written into exported case metadata (agent-evals contract).
CASE_ORIGIN_PRODUCTION = "production-finding"

# Rubric skeletons per signal type: deterministic scaffolding for the operator.
RUBRIC_SKELETONS: dict[str, str] = {
    SIGNAL_CORRECTION_FOLLOWUP: (
        "答案必须针对用户的修正点重新作答，并引用至少一条证据支持修正后的结论。"
    ),
    SIGNAL_MODE_SWITCH_REASK: (
        "必须使用用户指定的执行模式回答该问题，结论质量与证据引用不得低于原模式。"
    ),
    SIGNAL_EVIDENCE_GAP: "答案必须引用至少一条检索到的文档证据，且引用与结论一一对应。",
}
DEFAULT_RUBRIC_SKELETON = "答案必须完整回应该问题并引用支持结论的证据。"

# Signals whose failure mode is evidence-related, so drafts demand evidence.
EVIDENCE_REQUIRED_SIGNALS = frozenset({SIGNAL_CORRECTION_FOLLOWUP, SIGNAL_EVIDENCE_GAP})

# Drafts suggest the canonical fixture; the operator decides where it lands.
SUGGESTED_FIXTURE_PATH = "tests/evals/fixtures/agent_task_eval_set_v1.jsonl"


def list_feedback_findings(
    *, project_uid: str | None = None, db_name: str = "./database.sqlite"
) -> list[dict[str, Any]]:
    """List recurring signal findings (count, latest sample, related documents)."""
    return aggregate_feedback_findings(project_uid=project_uid, db_name=db_name)


def build_feedback_case_draft(*, finding_id: str, db_name: str = "./database.sqlite") -> dict[str, Any]:
    """Build one JSONL case draft from the finding's latest original question.

    The prompt is re-read from the durable run row (the feedback table keeps
    digests and previews only). Raises KeyError for unknown findings.
    """
    finding = find_finding_by_id(finding_id=str(finding_id), db_name=db_name)
    if finding is None:
        raise KeyError(f"Unknown feedback finding: {finding_id}")
    latest = latest_event_for_finding(
        project_uid=finding["project_uid"],
        signal_type=finding["signal_type"],
        doc_uid=finding["doc_uid"],
        db_name=db_name,
    )
    if latest is None:
        raise KeyError(f"Feedback finding has no events: {finding_id}")
    run = get_feedback_run_row(run_uid=latest["latest_run_uid"], db_name=db_name)
    prompt_from_run = str((run or {}).get("prompt") or "").strip()
    prompt = prompt_from_run or str(latest.get("latest_prompt_preview") or "")
    signal_type = str(finding["signal_type"])
    case = {
        "id": f"prod_{signal_type}_{str(finding_id)[3:11]}",
        "category": f"production/{signal_type}",
        "prompt": prompt,
        "success_rubric": RUBRIC_SKELETONS.get(signal_type, DEFAULT_RUBRIC_SKELETON),
        "requires_evidence": signal_type in EVIDENCE_REQUIRED_SIGNALS,
        "origin": CASE_ORIGIN_PRODUCTION,
        "finding_id": str(finding_id),
        "signal_type": signal_type,
        "source_run_uid": latest["latest_run_uid"],
        "exported_at": datetime.now(UTC).isoformat(),
    }
    return {
        "finding_id": str(finding_id),
        "signal_type": signal_type,
        "repeat_count": int(finding["repeat_count"]),
        "suggested_fixture_path": SUGGESTED_FIXTURE_PATH,
        "prompt_truncated": bool(not prompt_from_run),
        "case": case,
        "jsonl_line": json.dumps(case, ensure_ascii=False),
    }


__all__ = [
    "CASE_ORIGIN_PRODUCTION",
    "RUBRIC_SKELETONS",
    "build_feedback_case_draft",
    "list_feedback_findings",
]
