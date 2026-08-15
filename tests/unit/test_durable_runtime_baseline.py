"""Baseline metrics harness contract for the durable runtime migration."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select, update

from agent.adapters.orm.baseline_metrics_repository import get_baseline_metrics
from agent.adapters.orm.database import create_engine
from agent.adapters.orm.models import agent_run_events, agent_runs, agent_task_attempts
from agent.adapters.orm.run_repository import (
    append_run_item_event,
    append_run_lifecycle_event,
    update_run_status,
)
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.domain.agent_task import AgentTaskKind


def _iso(delta_seconds: float = 0.0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=delta_seconds)).isoformat()


def _backdate_run(*, run_uid: str, database: str, updated_at: str) -> None:
    engine = create_engine(database)
    try:
        with engine.begin() as connection:
            connection.execute(
                update(agent_runs).where(agent_runs.c.run_uid == run_uid).values(updated_at=updated_at)
            )
    finally:
        engine.dispose()


def _insert_finished_attempt(
    *, task_uid: str, database: str, started_at: str, finished_at: str, attempt_number: int = 1
) -> None:
    engine = create_engine(database)
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(agent_task_attempts).values(
                    attempt_uid=f"attempt_{uuid.uuid4().hex}",
                    task_uid=task_uid,
                    worker_id="baseline-worker",
                    attempt_number=attempt_number,
                    status="completed",
                    lease_expires_at=_iso(60),
                    heartbeat_at=started_at,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )
    finally:
        engine.dispose()


def _inject_duplicate_item_terminal(*, run_uid: str, item_uid: str, task_uid: str, database: str) -> None:
    """Write a second terminal item row directly; the repository rejects these now."""
    engine = create_engine(database)
    try:
        with engine.begin() as connection:
            sequence = connection.execute(
                select(func.coalesce(func.max(agent_run_events.c.sequence), 0) + 1).where(agent_run_events.c.run_uid == run_uid)
            ).scalar_one()
            item_payload = {
                "id": item_uid,
                "type": "agent_task",
                "status": "completed",
                "taskId": task_uid,
                "payload": {"summary": "重复终态"},
            }
            connection.execute(
                insert(agent_run_events).values(
                    event_uid=f"evt_{uuid.uuid4().hex}",
                    run_uid=run_uid,
                    sequence=sequence,
                    event_type="item.completed",
                    timestamp=_iso(),
                    payload_json=json.dumps({"item": item_payload}, ensure_ascii=False),
                    schema_version=2,
                    item_uid=item_uid,
                    task_uid=task_uid,
                )
            )
    finally:
        engine.dispose()


def test_baseline_metrics_report_counts_fixture_facts(tmp_path: Path) -> None:
    database = str(tmp_path / "baseline.sqlite")

    # 1. A completed run with a real leased attempt and item lifecycle events.
    completed_run, completed_leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="baseline-completed",
        prompt="完成的研究",
        input_payload={"prompt": "完成的研究"},
        db_name=database,
    )
    completed_uid = str(completed_run["run_uid"])
    append_run_lifecycle_event(run_uid=completed_uid, event_type="run.started", payload={}, db_name=database)
    append_run_item_event(
        run_uid=completed_uid,
        item_uid="item_assistant_message_text-0",
        item_type="assistant_message",
        status="in_progress",
        event_type="item.created",
        payload={"partId": "text-0", "text": ""},
        db_name=database,
    )
    append_run_item_event(
        run_uid=completed_uid,
        item_uid="item_assistant_message_text-0",
        item_type="assistant_message",
        status="completed",
        event_type="item.completed",
        payload={"partId": "text-0", "text": "答案"},
        db_name=database,
    )
    update_run_status(run_uid=completed_uid, status="completed", db_name=database)
    append_run_lifecycle_event(run_uid=completed_uid, event_type="run.completed", payload={}, db_name=database)

    # 2. A failed run whose terminal failure event was recorded twice.
    failed_run, _leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="baseline-failed",
        prompt="失败的研究",
        input_payload={"prompt": "失败的研究"},
        db_name=database,
    )
    update_run_status(run_uid=str(failed_run["run_uid"]), status="failed", error_message="x", db_name=database)
    for _ in range(2):
        append_run_lifecycle_event(
            run_uid=str(failed_run["run_uid"]), event_type="run.failed", payload={"message": "失败"}, db_name=database
        )

    # 3. A stalled run: queued with a fresh row but an outdated updated_at.
    stalled_run, _leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="baseline-stalled",
        prompt="停滞的研究",
        input_payload={"prompt": "停滞的研究"},
        db_name=database,
    )
    _backdate_run(run_uid=str(stalled_run["run_uid"]), database=database, updated_at=_iso(-3600))

    # 4. A recovered continuation run (resumed then completed) and one still unfinished.
    resumed_run, _leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="baseline-resumed",
        prompt="恢复的研究",
        input_payload={"prompt": "恢复的研究"},
        db_name=database,
    )
    append_run_lifecycle_event(run_uid=str(resumed_run["run_uid"]), event_type="run.resumed", payload={}, db_name=database)
    update_run_status(run_uid=str(resumed_run["run_uid"]), status="completed", db_name=database)
    unfinished_run, _leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="baseline-unfinished",
        prompt="未完成恢复",
        input_payload={"prompt": "未完成恢复"},
        db_name=database,
    )
    append_run_lifecycle_event(
        run_uid=str(unfinished_run["run_uid"]), event_type="run.resumed", payload={}, db_name=database
    )

    # 5. Two delegated child tasks, one with a duplicated terminal item event.
    child_one, _ = create_agent_task(
        run_uid=str(completed_run["run_uid"]),
        parent_task_uid=str(completed_leader["task_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="baseline-child-1",
        input_payload={"objective": "检索"},
        db_name=database,
    )
    child_two, _ = create_agent_task(
        run_uid=str(completed_run["run_uid"]),
        parent_task_uid=str(completed_leader["task_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="baseline-child-2",
        input_payload={"objective": "复核"},
        db_name=database,
    )
    append_run_item_event(
        run_uid=completed_uid,
        item_uid=f"item_agent_task_{child_one['task_uid']}",
        item_type="agent_task",
        task_uid=str(child_one["task_uid"]),
        status="completed",
        event_type="item.completed",
        payload={"summary": "重复终态"},
        db_name=database,
    )
    _inject_duplicate_item_terminal(
        run_uid=completed_uid,
        item_uid=f"item_agent_task_{child_one['task_uid']}",
        task_uid=str(child_one["task_uid"]),
        database=database,
    )

    # 6. Deterministic attempt latencies: 100ms, 200ms, 300ms.
    base = datetime.now(UTC) - timedelta(minutes=5)
    _insert_finished_attempt(
        task_uid=str(child_one["task_uid"]),
        database=database,
        started_at=base.isoformat(),
        finished_at=(base + timedelta(milliseconds=100)).isoformat(),
    )
    _insert_finished_attempt(
        task_uid=str(child_two["task_uid"]),
        database=database,
        started_at=base.isoformat(),
        finished_at=(base + timedelta(milliseconds=300)).isoformat(),
    )
    _insert_finished_attempt(
        task_uid=str(completed_leader["task_uid"]),
        database=database,
        started_at=base.isoformat(),
        finished_at=(base + timedelta(milliseconds=200)).isoformat(),
        attempt_number=2,
    )

    metrics = get_baseline_metrics(db_name=database, stalled_after_seconds=300.0)

    assert metrics["runs"]["status_counts"] == {"completed": 2, "failed": 1, "queued": 2}
    assert metrics["runs"]["stalled"] == 1
    assert metrics["runs"]["success_rate"] == round(2 / 3, 4)
    assert metrics["tasks"]["delegation_count"] == 2
    assert [
        (entry["run_uid"], entry["event_type"], entry["occurrences"])
        for entry in metrics["events"]["duplicate_lifecycle_events"]
    ] == [(str(failed_run["run_uid"]), "run.failed", 2)]
    assert [
        (entry["item_uid"], entry["occurrences"])
        for entry in metrics["events"]["duplicate_item_terminal_events"]
    ] == [(f"item_agent_task_{child_one['task_uid']}", 2)]
    assert metrics["reconnect_recovery"] == {"resumed_runs": 2, "resumed_completed": 1, "resumed_unfinished": 1}
    latency = metrics["task_latency_ms"]
    assert latency["samples"] == 3
    assert latency["median"] == pytest.approx(200.0, abs=1.0)
    assert latency["p95"] == pytest.approx(300.0, abs=1.0)
    assert metrics["events"]["total"] > 0

