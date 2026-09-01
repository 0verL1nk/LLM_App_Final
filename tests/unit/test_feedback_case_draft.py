"""Findings aggregation, operator case drafts, origin metadata, and report layering."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.adapters.orm.feedback_repository import (
    aggregate_feedback_findings,
    finding_id_for,
    record_feedback_event,
)
from agent.adapters.orm.run_repository import create_run
from agent.application.evals.contracts import AgentEvalCase
from agent.application.evals.loader import load_eval_cases
from agent.application.evals.reporting import build_eval_report
from agent.application.feedback_findings import (
    CASE_ORIGIN_PRODUCTION,
    build_feedback_case_draft,
    list_feedback_findings,
)
from agent.feedback.rules import (
    SIGNAL_CORRECTION_FOLLOWUP,
    SIGNAL_EVIDENCE_GAP,
    prompt_digest,
)

_PROJECT = "project-1"
_SESSION = "session-1"
_USER = "user-1"
_PROMPT = "帮我总结这篇论文提出的方法与实验结论"


def _make_run(database: str, request_id: str, prompt: str = _PROMPT) -> str:
    run, _created = create_run(
        project_uid=_PROJECT,
        session_uid=_SESSION,
        user_uuid=_USER,
        client_request_id=request_id,
        prompt=prompt,
        db_name=database,
    )
    return str(run["run_uid"])


def _record(database: str, run_uid: str, *, signal_type: str, doc_uid: str = "") -> str:
    event_uid, _created = record_feedback_event(
        user_uuid=_USER,
        project_uid=_PROJECT,
        session_uid=_SESSION,
        run_uid=run_uid,
        signal_type=signal_type,
        prompt_digest=prompt_digest(_PROMPT),
        trigger_digest=f"{signal_type}:{run_uid}",
        doc_uid=doc_uid,
        payload={
            "prompt_preview": _PROMPT,
            "doc_uids": [doc_uid] if doc_uid else [],
        },
        db_name=database,
    )
    return event_uid


def test_findings_require_min_repeats_within_window(tmp_path: Path) -> None:
    database = str(tmp_path / "findings.sqlite")
    run_a = _make_run(database, "request-001")
    run_b = _make_run(database, "request-002")
    other_run = _make_run(database, "request-003")
    _record(database, run_a, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")
    _record(database, run_b, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")
    _record(database, other_run, signal_type=SIGNAL_CORRECTION_FOLLOWUP)  # 只出现一次

    findings = list_feedback_findings(db_name=database)

    assert [finding["repeat_count"] for finding in findings] == [2]
    finding = findings[0]
    assert finding["signal_type"] == SIGNAL_EVIDENCE_GAP
    assert finding["doc_uid"] == "doc-1"
    assert finding["finding_id"] == finding_id_for(
        project_uid=_PROJECT, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1"
    )
    assert finding["latest_prompt_preview"] == _PROMPT
    assert finding["related_doc_uids"] == ["doc-1"]


def test_findings_bucket_only_events_inside_the_time_window(tmp_path: Path) -> None:
    database = str(tmp_path / "findings.sqlite")
    run_a = _make_run(database, "request-001")
    run_b = _make_run(database, "request-002")
    _record(database, run_a, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")
    _record(database, run_b, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")
    _age_event_outside_window(database, run_a)  # run_a 的事件移出时间窗

    recent_only = aggregate_feedback_findings(window_days=30, db_name=database)
    wide_window = aggregate_feedback_findings(window_days=90, db_name=database)

    assert recent_only == []  # 窗内只剩 1 次，低于最小重复阈值
    assert [finding["repeat_count"] for finding in wide_window] == [2]


def _age_event_outside_window(database: str, run_uid: str) -> None:
    from sqlalchemy import update

    from agent.adapters.orm.database import create_engine
    from agent.adapters.orm.models import feedback_events

    stale = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    engine = create_engine(database)
    try:
        with engine.begin() as connection:
            connection.execute(
                update(feedback_events)
                .where(feedback_events.c.run_uid == run_uid)
                .values(created_at=stale)
            )
    finally:
        engine.dispose()


def test_export_case_draft_carries_original_prompt_and_origin(tmp_path: Path) -> None:
    database = str(tmp_path / "findings.sqlite")
    run_a = _make_run(database, "request-001", prompt=_PROMPT)
    run_b = _make_run(database, "request-002", prompt=_PROMPT)
    _record(database, run_a, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")
    _record(database, run_b, signal_type=SIGNAL_EVIDENCE_GAP, doc_uid="doc-1")

    finding = list_feedback_findings(db_name=database)[0]
    draft = build_feedback_case_draft(finding_id=finding["finding_id"], db_name=database)

    assert draft["signal_type"] == SIGNAL_EVIDENCE_GAP
    assert draft["repeat_count"] == 2
    assert draft["suggested_fixture_path"].endswith(".jsonl")
    assert draft["prompt_truncated"] is False
    case = draft["case"]
    # prompt 取最近一次的原始问题（从 run 行重读，而非脱敏预览）。
    assert case["prompt"] == _PROMPT
    assert case["origin"] == CASE_ORIGIN_PRODUCTION
    assert case["finding_id"] == finding["finding_id"]
    assert case["source_run_uid"] in {run_a, run_b}
    assert "引用" in case["success_rubric"]
    assert case["requires_evidence"] is True
    assert json.loads(draft["jsonl_line"]) == case

    # 草稿行能被 fixture loader 消化，origin 进入 metadata。
    loaded = AgentEvalCase.from_dict(dict(case))
    assert loaded.metadata["origin"] == CASE_ORIGIN_PRODUCTION
    assert loaded.metadata["finding_id"] == finding["finding_id"]


def test_export_case_draft_rejects_unknown_finding(tmp_path: Path) -> None:
    database = str(tmp_path / "findings.sqlite")

    try:
        build_feedback_case_draft(finding_id="fb_unknown", db_name=database)
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_loader_round_trips_production_case_draft(tmp_path: Path) -> None:
    database = str(tmp_path / "findings.sqlite")
    run_uid = _make_run(database, "request-001")
    _record(database, run_uid, signal_type=SIGNAL_CORRECTION_FOLLOWUP)
    fixture = tmp_path / "fixture.jsonl"
    draft = build_feedback_case_draft(
        finding_id=finding_id_for(
            project_uid=_PROJECT, signal_type=SIGNAL_CORRECTION_FOLLOWUP, doc_uid=""
        ),
        db_name=database,
    )
    fixture.write_text(
        json.dumps({"id": "authored-1", "category": "fact", "prompt": "自写用例",
                    "success_rubric": "回答需覆盖问题"}, ensure_ascii=False)
        + "\n"
        + draft["jsonl_line"]
        + "\n",
        encoding="utf-8",
    )

    cases = load_eval_cases(fixture)

    assert [case.case_id for case in cases] == ["authored-1", draft["case"]["id"]]
    assert cases[1].metadata["origin"] == CASE_ORIGIN_PRODUCTION


def test_report_layers_completion_rates_by_case_origin() -> None:
    report = build_eval_report(
        fixture_path="fixture.jsonl",
        case_results=[
            {
                "case_id": "prod-1",
                "completed": True,
                "final_success": True,
                "metadata": {"origin": CASE_ORIGIN_PRODUCTION},
            },
            {
                "case_id": "authored-1",
                "completed": False,
                "final_success": False,
                "metadata": {},
            },
        ],
    )

    breakdown = report["origin_breakdown"]
    assert breakdown[CASE_ORIGIN_PRODUCTION]["total"] == 1
    assert breakdown[CASE_ORIGIN_PRODUCTION]["completion_rate"] == 1.0
    assert breakdown["authored"]["total"] == 1
    assert breakdown["authored"]["completion_rate"] == 0.0
