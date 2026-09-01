"""Durable feedback capture: enqueue, deterministic worker, idempotency, redaction."""

import json
import time
from pathlib import Path

from agent.adapters.orm.feedback_repository import (
    aggregate_feedback_findings,
    claim_feedback_analysis_task,
    complete_feedback_analysis_task,
    enqueue_feedback_analysis_task,
    list_run_steering_inputs,
    record_evidence_click,
    record_feedback_event,
)
from agent.adapters.orm.run_repository import create_run, update_run_status
from agent.application.steering_inputs import queue_steering_input
from agent.feedback.analysis import process_feedback_analysis
from agent.feedback.rules import (
    PREVIEW_MAX_CHARS,
    SIGNAL_CORRECTION_FOLLOWUP,
    SIGNAL_EVIDENCE_GAP,
    SIGNAL_MODE_SWITCH_REASK,
    event_idempotency_key,
    prompt_digest,
)

_PROJECT = "project-1"
_SESSION = "session-1"
_USER = "user-1"
_PROMPT = "帮我总结这篇论文提出的方法与实验结论"


def _make_run(database: str, *, prompt: str, requested_mode: str = "auto", request_id: str) -> dict:
    run, _created = create_run(
        project_uid=_PROJECT,
        session_uid=_SESSION,
        user_uuid=_USER,
        client_request_id=request_id,
        prompt=prompt,
        requested_mode=requested_mode,
        db_name=database,
    )
    assert update_run_status(run_uid=str(run["run_uid"]), status="running", db_name=database)
    return run


def _enqueue(database: str, run: dict, **overrides: object) -> str:
    kwargs = {
        "run_uid": str(run["run_uid"]),
        "user_uuid": _USER,
        "project_uid": _PROJECT,
        "session_uid": _SESSION,
        "citation_audit": "not_applicable",
        "retrieved_evidence_count": 0,
        "evidence_doc_uids": [],
        "db_name": database,
    }
    kwargs.update(overrides)
    task, created = enqueue_feedback_analysis_task(**kwargs)
    assert created is True
    return str(task["task_uid"])


def test_analysis_task_enqueue_is_idempotent_per_run(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")

    first, created_first = enqueue_feedback_analysis_task(
        run_uid=str(run["run_uid"]),
        user_uuid=_USER,
        project_uid=_PROJECT,
        session_uid=_SESSION,
        db_name=database,
    )
    second, created_second = enqueue_feedback_analysis_task(
        run_uid=str(run["run_uid"]),
        user_uuid=_USER,
        project_uid=_PROJECT,
        session_uid=_SESSION,
        db_name=database,
    )

    assert created_first is True
    assert created_second is False
    assert second["task_uid"] == first["task_uid"]


def test_worker_records_redacted_correction_followup(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")
    # 超过预览上限的长追问：事件里只允许出现截断预览，不允许全文。
    steering_text = "不对，" + "请重新核对方法与实验部分的描述，并补充对比实验的说明，" * 5
    assert len(steering_text) > PREVIEW_MAX_CHARS
    queue_steering_input(
        project_uid=_PROJECT,
        session_uid=_SESSION,
        user_uuid=_USER,
        client_request_id="follow-up-001",
        text=steering_text,
        db_name=database,
    )
    task_uid = _enqueue(database, run)

    process_feedback_analysis(task_uid, db_name=database)

    events = _raw_run_events(database, str(run["run_uid"]))
    assert [event["signal_type"] for event in events] == [SIGNAL_CORRECTION_FOLLOWUP]
    payload = events[0]["payload"]
    assert payload["rule"] == "leading_word"
    assert 0 < len(payload["steering_preview"]) <= PREVIEW_MAX_CHARS
    # 脱敏：事件里只有摘要与指纹，绝不落 steering 全文。
    assert steering_text not in json.dumps(events[0], ensure_ascii=False)
    assert events[0]["prompt_digest"] == prompt_digest(_PROMPT)

    # 幂等：同一 (user, run, signal, digest) 只落一行；完成的任务不可再次认领。
    event_kwargs = {
        "user_uuid": _USER,
        "project_uid": _PROJECT,
        "session_uid": _SESSION,
        "run_uid": str(run["run_uid"]),
        "signal_type": SIGNAL_CORRECTION_FOLLOWUP,
        "prompt_digest": events[0]["prompt_digest"],
        "trigger_digest": "digest-x",
        "payload": {},
        "db_name": database,
    }
    first_uid, first_created = record_feedback_event(**event_kwargs)
    same_uid, created_again = record_feedback_event(**event_kwargs)
    assert first_created is True
    assert created_again is False and same_uid == first_uid
    assert claim_feedback_analysis_task(task_uid=task_uid, db_name=database) is None


def test_worker_records_mode_switch_against_previous_run(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    first_run = _make_run(database, prompt=_PROMPT, requested_mode="fast", request_id="request-001")
    assert update_run_status(run_uid=str(first_run["run_uid"]), status="completed", db_name=database)
    time.sleep(0.01)  # created_at 毫秒级排序，保证相邻两轮可区分
    run = _make_run(database, prompt=_PROMPT + "（英文）", requested_mode="deep", request_id="request-002")
    task_uid = _enqueue(database, run)

    process_feedback_analysis(task_uid, db_name=database)

    events = _raw_run_events(database, str(run["run_uid"]))
    assert [event["signal_type"] for event in events] == [SIGNAL_MODE_SWITCH_REASK]
    assert events[0]["payload"]["requested_mode"] == "deep"
    assert events[0]["payload"]["previous_requested_mode"] == "fast"


def test_worker_records_evidence_gap_only_on_failed_audit(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    failed_run = _make_run(database, prompt=_PROMPT, request_id="request-001")
    time.sleep(0.01)
    passed_run = _make_run(database, prompt="另一个独立的问题，关于数据集构建流程", request_id="request-002")

    process_feedback_analysis(
        _enqueue(database, failed_run, citation_audit="failed", retrieved_evidence_count=3,
                 evidence_doc_uids=["doc-9"]),
        db_name=database,
    )
    process_feedback_analysis(
        _enqueue(database, passed_run, citation_audit="passed", retrieved_evidence_count=3),
        db_name=database,
    )

    gap_events = _raw_run_events(database, str(failed_run["run_uid"]))
    assert [event["signal_type"] for event in gap_events] == [SIGNAL_EVIDENCE_GAP]
    assert gap_events[0]["doc_uid"] == "doc-9"
    assert gap_events[0]["payload"]["retrieved_evidence_count"] == 3
    assert _raw_run_events(database, str(passed_run["run_uid"])) == []


def test_worker_skips_when_run_row_is_missing(tmp_path: Path, monkeypatch) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")
    task_uid = _enqueue(database, run)
    from agent.feedback import analysis

    monkeypatch.setattr(analysis, "get_feedback_run_row", lambda **_kwargs: None)
    process_feedback_analysis(task_uid, db_name=database)

    assert _task_row(database, task_uid)["status"] == "completed"
    assert _raw_run_events(database, str(run["run_uid"])) == []
    assert aggregate_feedback_findings(db_name=database) == []


def test_failed_analysis_task_can_be_reclaimed(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")
    task_uid = _enqueue(database, run)
    claimed = claim_feedback_analysis_task(task_uid=task_uid, db_name=database)
    assert claimed is not None and claimed["status"] == "processing"
    assert claim_feedback_analysis_task(task_uid=task_uid, db_name=database) is None
    complete_feedback_analysis_task(task_uid=task_uid, status="failed", error_message="boom", db_name=database)

    reclaimed = claim_feedback_analysis_task(task_uid=task_uid, db_name=database)

    assert reclaimed is not None and reclaimed["status"] == "processing"
    assert reclaimed["error_message"] == ""


def test_evidence_click_records_for_owned_run_only(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")

    click_id = record_evidence_click(
        run_uid=str(run["run_uid"]), user_uuid=_USER, evidence_ref="doc-1:chunk_2", db_name=database
    )

    assert click_id > 0
    for run_uid, user in ((str(run["run_uid"]), "user-2"), ("run_missing", _USER)):
        try:
            record_evidence_click(
                run_uid=run_uid, user_uuid=user, evidence_ref="doc-1:chunk_2", db_name=database
            )
            raise AssertionError("expected LookupError")
        except LookupError:
            pass


def _raw_run_events(database: str, run_uid: str) -> list[dict]:
    import json

    from sqlalchemy import select

    from agent.adapters.orm.database import create_engine
    from agent.adapters.orm.models import feedback_events

    engine = create_engine(database)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(feedback_events).where(feedback_events.c.run_uid == run_uid)
            ).all()
            return [
                {
                    "signal_type": row.signal_type,
                    "prompt_digest": row.prompt_digest,
                    "doc_uid": row.doc_uid,
                    "payload": json.loads(row.payload_json),
                }
                for row in rows
            ]
    finally:
        engine.dispose()


def _task_row(database: str, task_uid: str) -> dict:
    from sqlalchemy import select

    from agent.adapters.orm.database import create_engine
    from agent.adapters.orm.models import feedback_analysis_tasks

    engine = create_engine(database)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(feedback_analysis_tasks).where(
                    feedback_analysis_tasks.c.task_uid == task_uid
                )
            ).one()
            return dict(row._mapping)
    finally:
        engine.dispose()


def test_idempotency_key_matches_repository_event_uid(tmp_path: Path) -> None:
    database = str(tmp_path / "feedback.sqlite")
    run = _make_run(database, prompt=_PROMPT, request_id="request-001")

    event_uid, _created = record_feedback_event(
        user_uuid=_USER,
        project_uid=_PROJECT,
        session_uid=_SESSION,
        run_uid=str(run["run_uid"]),
        signal_type=SIGNAL_EVIDENCE_GAP,
        prompt_digest=prompt_digest(_PROMPT),
        trigger_digest=prompt_digest(_PROMPT),
        payload={},
        db_name=database,
    )

    assert event_uid == event_idempotency_key(
        user_uuid=_USER,
        run_uid=str(run["run_uid"]),
        signal_type=SIGNAL_EVIDENCE_GAP,
        trigger_digest=prompt_digest(_PROMPT),
    )
    assert list_run_steering_inputs(run_uid=str(run["run_uid"]), db_name=database) == []
