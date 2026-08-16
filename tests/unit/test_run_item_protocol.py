"""Contract tests for the V2 run-item protocol: lifecycle, replay, redaction, terminal."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent.adapters.orm.run_repository import (
    append_run_event,
    append_run_item_event,
    append_run_lifecycle_event,
    claim_run_execution,
    create_run,
    get_run,
    get_run_item,
    list_run_events,
    list_run_items,
    update_run_status,
)
from agent.domain.run_item import (
    RunItemProtocolError,
    is_terminal_item_status,
    merge_item_payload,
    validate_item_event,
)
from api.main import app


def _forward_db(monkeypatch, module: Any, name: str, database: str) -> None:
    original = getattr(module, name)
    monkeypatch.setattr(module, name, lambda **kwargs: original(**kwargs, db_name=database))


def _make_run(database: str, request_id: str = "request-1") -> dict[str, Any]:
    run, _created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id=request_id,
        prompt="研究这个问题",
        db_name=database,
    )
    return dict(run)


def _stream_assistant_answer(run_uid: str, database: str) -> list[dict[str, Any]]:
    events = [
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="in_progress",
            event_type="item.delta",
            payload={"partId": "text-0", "delta": "第一段"},
            db_name=database,
        ),
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="in_progress",
            event_type="item.delta",
            payload={"partId": "text-0", "delta": "第二段"},
            db_name=database,
        ),
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="completed",
            event_type="item.completed",
            payload={"partId": "text-0", "text": "第一段第二段"},
            db_name=database,
        ),
    ]
    return events


def _count_events(run_uid: str, database: str) -> int:
    with sqlite3.connect(database) as connection:
        return int(
            connection.execute("SELECT COUNT(*) FROM agent_run_events WHERE run_uid = ?", (run_uid,)).fetchone()[0]
        )


def test_item_lifecycle_orders_deltas_before_exactly_one_terminal(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])

    events = _stream_assistant_answer(run_uid, database)

    assert [event["eventType"] for event in events] == ["item.delta", "item.delta", "item.completed"]
    assert [event["sequence"] for event in events] == sorted(event["sequence"] for event in events)
    item = get_run_item(run_uid=run_uid, item_uid="item_assistant_message_text-0", db_name=database)
    assert item is not None
    assert item["status"] == "completed"
    assert item["payload"]["text"] == "第一段第二段"
    assert is_terminal_item_status(item["status"])


def test_lifecycle_violations_are_rejected_before_persistence(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    _stream_assistant_answer(run_uid, database)
    persisted = _count_events(run_uid, database)

    with pytest.raises(RunItemProtocolError):
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="in_progress",
            event_type="item.delta",
            payload={"partId": "text-0", "delta": "迟到的增量"},
            db_name=database,
        )
    with pytest.raises(RunItemProtocolError):
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="completed",
            event_type="item.completed",
            payload={"partId": "text-0", "text": "重复终止"},
            db_name=database,
        )
    with pytest.raises(RunItemProtocolError):
        append_run_item_event(
            run_uid=run_uid,
            item_uid="item_assistant_message_text-0",
            item_type="assistant_message",
            status="in_progress",
            event_type="item.created",
            payload={"partId": "text-0"},
            db_name=database,
        )
    assert _count_events(run_uid, database) == persisted
    item = get_run_item(run_uid=run_uid, item_uid="item_assistant_message_text-0", db_name=database)
    assert item is not None
    assert item["payload"]["text"] == "第一段第二段"


def test_unknown_item_type_status_and_event_type_are_rejected(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    persisted = _count_events(run_uid, database)

    invalid_calls: list[dict[str, Any]] = [
        {"item_type": "survey_note", "status": "in_progress", "event_type": "item.created"},
        {"item_type": "tool_call", "status": "paused", "event_type": "item.created"},
        {"item_type": "tool_call", "status": "in_progress", "event_type": "item.updated"},
        {"item_type": "tool_call", "status": "in_progress", "event_type": "item.completed"},
        {"item_type": "tool_call", "status": "completed", "event_type": "item.delta"},
    ]
    for kwargs in invalid_calls:
        with pytest.raises(RunItemProtocolError):
            append_run_item_event(
                run_uid=run_uid,
                item_uid="item_invalid",
                payload={"summary": "无效事件"},
                db_name=database,
                **kwargs,
            )
    assert _count_events(run_uid, database) == persisted
    assert get_run_item(run_uid=run_uid, item_uid="item_invalid", db_name=database) is None
    with pytest.raises(RunItemProtocolError):
        validate_item_event(
            item_uid="item-x",
            item_type="assistant_message",
            status="in_progress",
            event_type="item.delta",
            payload={"partId": "text-0", "delta": 17},
        )


def test_replay_after_seq_is_ordered_and_never_duplicates(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    claim_run_execution(run_uid=run_uid, db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.started", payload={"status": "running"}, db_name=database)
    _stream_assistant_answer(run_uid, database)
    update_run_status(run_uid=run_uid, status="completed", db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": {}}, db_name=database)

    full = list_run_events(run_uid=run_uid, after_sequence=0, db_name=database)
    replayed = list_run_events(run_uid=run_uid, after_sequence=0, db_name=database)
    assert full == replayed
    assert [event["sequence"] for event in full] == sorted({event["sequence"] for event in full})
    assert len({event["eventId"] for event in full}) == len(full)
    partial = list_run_events(run_uid=run_uid, after_sequence=full[2]["sequence"], db_name=database)
    assert [event["sequence"] for event in partial] == [event["sequence"] for event in full[3:]]

    rebuilt: dict[str, dict[str, Any]] = {}
    for event in full:
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_uid = str(item["id"])
        state = rebuilt.setdefault(item_uid, {"type": item["type"], "status": "", "payload": {}})
        state["status"] = str(item["status"])
        state["payload"] = merge_item_payload(
            state["payload"],
            item_type=str(item["type"]),
            event_type=str(event["eventType"]),
            payload=dict(item["payload"]),
        )
    snapshot = list_run_items(run_uid=run_uid, db_name=database)
    assert {item["id"] for item in snapshot["items"]} == set(rebuilt)
    for item in snapshot["items"]:
        state = rebuilt[item["id"]]
        assert item["type"] == state["type"]
        assert item["status"] == state["status"]
        assert item["payload"] == state["payload"]


def test_item_payloads_strip_credential_keys(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])

    append_run_item_event(
        run_uid=run_uid,
        item_uid="item_plan_plan-1",
        item_type="plan",
        status="in_progress",
        event_type="item.created",
        payload={
            "summary": "更新计划",
            "toolName": "update_plan",
            "plan": {
                "goal": "对比两篇论文",
                "steps": [{"id": "s1", "title": "检索", "status": "pending", "depends_on": [], "lane": "main"}],
            },
            "api_key": "sk-should-not-persist",
            "nested": {"authorization": "Bearer should-not-persist", "token": "t", "safe": "保留"},
        },
        db_name=database,
    )

    item = get_run_item(run_uid=run_uid, item_uid="item_plan_plan-1", db_name=database)
    assert item is not None
    serialized = json.dumps(item["payload"], ensure_ascii=False)
    for secret in ("sk-should-not-persist", "Bearer should-not-persist", '"token"'):
        assert secret not in serialized
    assert item["payload"]["nested"]["safe"] == "保留"
    public = next(
        event for event in list_run_events(run_uid=run_uid, db_name=database) if event.get("item")
    )
    assert "sk-should-not-persist" not in json.dumps(public["item"]["payload"], ensure_ascii=False)


def test_terminal_run_event_follows_final_item_and_matches_run_status(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    claim_run_execution(run_uid=run_uid, db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.started", payload={"status": "running"}, db_name=database)
    _stream_assistant_answer(run_uid, database)
    update_run_status(run_uid=run_uid, status="completed", db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": {}}, db_name=database)

    events = list_run_events(run_uid=run_uid, db_name=database)
    assert events[-1]["eventType"] == "run.completed"
    item_sequences = [event["sequence"] for event in events if event.get("item")]
    assert events[-1]["sequence"] > max(item_sequences)
    assert get_run(run_uid=run_uid, user_uuid="user-1", db_name=database)["status"] == "completed"


def test_failed_leader_run_emits_durable_failure_item_before_run_failed(monkeypatch, tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])

    from agent.application import research_workspace, run_execution

    monkeypatch.setattr(run_execution, "claim_run_execution", lambda **_kwargs: True)
    _forward_db(monkeypatch, run_execution, "update_run_status", database)
    _forward_db(monkeypatch, run_execution, "append_run_lifecycle_event", database)
    _forward_db(monkeypatch, run_execution, "append_run_item_event", database)
    monkeypatch.setattr(
        research_workspace.research_workspace_service,
        "execute_turn",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider exploded")),
    )
    with pytest.raises(RuntimeError):
        run_execution.execute_research_run(
            run_uid=run_uid,
            project_uid="project-1",
            session_uid="session-1",
            user_uuid="user-1",
            prompt="问题",
        )

    events = list_run_events(run_uid=run_uid, db_name=database)
    item_events = [event for event in events if event.get("item")]
    assert [event["eventType"] for event in item_events] == ["item.failed"]
    assert item_events[0]["item"]["type"] == "failure"
    assert events[-1]["eventType"] == "run.failed"
    assert events[-1]["sequence"] > item_events[0]["sequence"]
    assert get_run(run_uid=run_uid, user_uuid="user-1", db_name=database)["status"] == "failed"


def test_items_snapshot_feeds_afterseq_replay_cursor(tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    _stream_assistant_answer(run_uid, database)

    snapshot = list_run_items(run_uid=run_uid, db_name=database)
    assert snapshot["lastSequence"] == max(event["sequence"] for event in list_run_events(run_uid=run_uid, db_name=database))
    assert snapshot["items"][0]["sequence"] == snapshot["lastSequence"]
    assert list_run_items(run_uid=run_uid, after_sequence=snapshot["lastSequence"], db_name=database)["items"] == []

    update_run_status(run_uid=run_uid, status="completed", db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": {}}, db_name=database)
    later = list_run_items(run_uid=run_uid, after_sequence=snapshot["lastSequence"], db_name=database)
    assert later["items"] == []
    replay = list_run_events(run_uid=run_uid, after_sequence=snapshot["lastSequence"], db_name=database)
    assert [event["eventType"] for event in replay] == ["run.completed"]

    append_run_item_event(
        run_uid=run_uid,
        item_uid="item_tool_call_call-9",
        item_type="tool_call",
        status="in_progress",
        event_type="item.created",
        payload={"summary": "补充检索", "toolName": "search_document"},
        db_name=database,
    )
    incremental = list_run_items(run_uid=run_uid, after_sequence=snapshot["lastSequence"], db_name=database)
    assert [item["id"] for item in incremental["items"]] == ["item_tool_call_call-9"]
    assert incremental["lastSequence"] > snapshot["lastSequence"]


def test_continuation_parts_get_scoped_item_ids(monkeypatch, tmp_path: Path) -> None:
    database = str(tmp_path / "protocol.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    from agent.adapters.orm.task_dispatch_repository import create_agent_task

    task, _created = create_agent_task(
        run_uid=run_uid,
        parent_task_uid=None,
        kind="continuation",
        agent_role="",
        idempotency_key="continuation-1",
        input_payload={"parent_task_uid": "task-parent", "tool_results": []},
        db_name=database,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE agent_tasks SET continuation_epoch = 1 WHERE task_uid = ?", (task["task_uid"],)
        )

    from agent.application import research_workspace, run_execution

    captured: dict[str, Any] = {}

    def fake_continuation_turn(**kwargs: Any) -> dict[str, Any]:
        captured["part_scope"] = kwargs.get("part_scope")
        return {"answer": "整合完成", "response_parts": []}

    _forward_db(monkeypatch, run_execution, "update_run_status", database)
    _forward_db(monkeypatch, run_execution, "append_run_lifecycle_event", database)
    _forward_db(monkeypatch, run_execution, "get_run", database)
    monkeypatch.setattr(
        research_workspace.research_workspace_service,
        "execute_continuation_turn",
        fake_continuation_turn,
    )
    run_execution.execute_research_continuation(
        continuation_task_uid=str(task["task_uid"]),
        run_uid=run_uid,
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        parent_task_uid="task-parent",
        tool_results=[],
        db_name=database,
    )

    assert captured["part_scope"] == "e1"
    assert get_run(run_uid=run_uid, user_uuid="user-1", db_name=database)["status"] == "completed"


def _stream_client(monkeypatch, tmp_path: Path) -> tuple[TestClient, dict[str, Any], str]:
    database = str(tmp_path / "sse.sqlite")
    run = _make_run(database)
    run_uid = str(run["run_uid"])
    append_run_event(run_uid=run_uid, event_type="message.part.delta", payload={"text": "旧协议"}, db_name=database)
    _stream_assistant_answer(run_uid, database)
    update_run_status(run_uid=run_uid, status="completed", db_name=database)
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": {}}, db_name=database)

    from api import run_routes

    original_get_run = run_routes.get_run
    original_list_events = run_routes.list_run_events
    monkeypatch.setattr(run_routes, "get_run", lambda **kwargs: original_get_run(**kwargs, db_name=database))
    monkeypatch.setattr(
        run_routes,
        "list_run_events",
        lambda **kwargs: original_list_events(**kwargs, db_name=database),
    )
    return TestClient(app), run, database


def _collect_sse_frames(client: TestClient, path: str, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    with client.stream("GET", path, headers={"X-User-Id": "user-1", **(headers or {})}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: ") :]))
    return frames


def test_sse_stream_serves_v2_only_without_negotiation(monkeypatch, tmp_path: Path) -> None:
    client, run, database = _stream_client(monkeypatch, tmp_path)
    run_uid = str(run["run_uid"])

    # The legacy V1 row stays readable from storage but never reaches the wire.
    stored = list_run_events(run_uid=run_uid, db_name=database)
    assert any(event["version"] == 1 and event["eventType"] == "message.part.delta" for event in stored)

    stream = _collect_sse_frames(client, f"/api/v1/runs/{run_uid}/events")
    assert {frame["version"] for frame in stream} == {2}
    assert all(frame["eventType"] != "message.part.delta" for frame in stream)
    assert [frame["eventType"] for frame in stream][-1] == "run.completed"

    with client.stream(
        "GET",
        f"/api/v1/runs/{run_uid}/events",
        headers={"X-User-Id": "user-1"},
    ) as response:
        assert response.headers["X-Run-Events-Version"] == "2"


def test_sse_afterseq_replay_only_returns_later_events(monkeypatch, tmp_path: Path) -> None:
    client, run, database = _stream_client(monkeypatch, tmp_path)
    run_uid = str(run["run_uid"])
    full = _collect_sse_frames(client, f"/api/v1/runs/{run_uid}/events")
    cursor = full[2]["sequence"]
    replay = _collect_sse_frames(client, f"/api/v1/runs/{run_uid}/events?afterSeq={cursor}")
    assert [frame["sequence"] for frame in replay] == [frame["sequence"] for frame in full[3:]]
