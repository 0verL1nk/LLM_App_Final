from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock, Thread

from agent.adapters.orm.run_repository import (
    append_run_event,
    append_run_item_event,
    create_run,
    list_run_events,
    list_run_items,
)
from agent.adapters.orm.task_attempt_repository import (
    claim_next_task,
    claim_task_by_uid,
    complete_task_attempt,
    mark_task_running,
    reclaim_expired_task_attempts,
)
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.adapters.orm.task_parent_repository import (
    create_join_continuation_if_ready,
    reconcile_completed_continuation_parents,
    wait_for_child_tasks,
)
from agent.adapters.orm.task_query_repository import (
    get_agent_task,
    get_agent_task_run_context,
    list_agent_task_attempts,
    request_run_cancel,
    request_task_cancel,
    retry_agent_task,
)
from agent.domain.agent_task import AgentTaskAttemptStatus, AgentTaskKind, AgentTaskStatus


def _run_uid(database: str) -> str:
    run, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="比较两篇论文",
        db_name=database,
    )
    assert created is True
    return str(run["run_uid"])


def test_task_submission_is_idempotent_but_same_role_can_run_concurrently(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    run_uid = _run_uid(database)
    first, first_created = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="methods-a",
        input_payload={"description": "核验实验设置"},
        db_name=database,
    )
    duplicate, duplicate_created = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="methods-a",
        input_payload={"description": "核验实验设置"},
        db_name=database,
    )
    second, second_created = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="methods-b",
        input_payload={"description": "核验实验设置"},
        db_name=database,
    )

    assert first_created is True
    assert duplicate_created is False
    assert duplicate["task_uid"] == first["task_uid"]
    assert second_created is True
    assert second["task_uid"] != first["task_uid"]


def test_task_run_context_derives_worker_scope_from_the_run(tmp_path: Path) -> None:
    database = str(tmp_path / "task-context.sqlite")
    run_uid = _run_uid(database)
    task, _ = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="scope",
        input_payload={"description": "收集证据", "user_uuid": "forged-user"},
        db_name=database,
    )

    context = get_agent_task_run_context(task_uid=str(task["task_uid"]), db_name=database)

    assert context is not None
    assert context["project_uid"] == "project-1"
    assert context["session_uid"] == "session-1"
    assert context["user_uuid"] == "user-1"
    assert context["input"]["user_uuid"] == "forged-user"


def test_leader_run_creates_run_task_and_outbox_as_one_idempotent_submission(tmp_path: Path) -> None:
    database = str(tmp_path / "leader.sqlite")
    run, leader, created = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="比较两篇论文",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "比较两篇论文"},
        db_name=database,
    )
    duplicate_run, duplicate_leader, duplicate_created = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="比较两篇论文",
        input_payload={"ignored": True},
        db_name=database,
    )

    assert created is True
    assert leader["kind"] == AgentTaskKind.LEADER.value
    assert leader["run_uid"] == run["run_uid"]
    assert duplicate_created is False
    assert duplicate_run["run_uid"] == run["run_uid"]
    assert duplicate_leader["task_uid"] == leader["task_uid"]
    assert list_run_events(run_uid=str(run["run_uid"]), db_name=database)[0]["eventType"] == "run.created"


def test_expired_attempt_cannot_overwrite_reclaimed_task(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    run_uid = _run_uid(database)
    task, _ = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="evidence",
        db_name=database,
    )

    first = claim_next_task(worker_id="worker-a", lease_seconds=1, db_name=database)
    assert first is not None
    first_attempt = str(first["current_attempt_uid"])
    assert mark_task_running(task_uid=task["task_uid"], attempt_uid=first_attempt, db_name=database)
    reclaimed = reclaim_expired_task_attempts(
        now=datetime.now(UTC) + timedelta(seconds=2), db_name=database
    )
    assert reclaimed == [task["task_uid"]]

    second = claim_next_task(worker_id="worker-b", lease_seconds=60, db_name=database)
    assert second is not None
    second_attempt = str(second["current_attempt_uid"])
    assert second_attempt != first_attempt
    assert mark_task_running(task_uid=task["task_uid"], attempt_uid=second_attempt, db_name=database)
    assert complete_task_attempt(
        task_uid=task["task_uid"], attempt_uid=first_attempt, result={"summary": "迟到结果"}, db_name=database
    ) is False
    assert complete_task_attempt(
        task_uid=task["task_uid"], attempt_uid=second_attempt, result={"summary": "有效结果"}, db_name=database
    ) is True

    persisted = get_agent_task(task_uid=task["task_uid"], db_name=database)
    assert persisted is not None
    assert persisted["status"] == AgentTaskStatus.COMPLETED.value
    assert persisted["result"] == {"summary": "有效结果"}
    assert [attempt["status"] for attempt in list_agent_task_attempts(task_uid=task["task_uid"], db_name=database)] == ["expired", "completed"]


def test_terminal_children_create_exactly_one_join_continuation(tmp_path: Path) -> None:
    database = str(tmp_path / "join-continuation.sqlite")
    run, leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="join-continuation",
        prompt="比较论文",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "比较论文"},
        db_name=database,
    )
    children = [
        create_agent_task(
            run_uid=str(run["run_uid"]),
            parent_task_uid=str(leader["task_uid"]),
            kind=AgentTaskKind.SUBAGENT,
            agent_role="researcher",
            idempotency_key=f"child-{index}",
            input_payload={"tool_call_id": f"call-{index}"},
            db_name=database,
        )[0]
        for index in range(2)
    ]
    leased_leader = claim_task_by_uid(task_uid=str(leader["task_uid"]), worker_id="leader", db_name=database)
    assert leased_leader is not None
    assert mark_task_running(task_uid=str(leader["task_uid"]), attempt_uid=leased_leader["current_attempt_uid"], db_name=database)
    assert wait_for_child_tasks(task_uid=str(leader["task_uid"]), attempt_uid=leased_leader["current_attempt_uid"], db_name=database)

    for index, child in enumerate(children):
        leased_child = claim_task_by_uid(task_uid=str(child["task_uid"]), worker_id=f"child-{index}", db_name=database)
        assert leased_child is not None
        assert complete_task_attempt(task_uid=str(child["task_uid"]), attempt_uid=leased_child["current_attempt_uid"], result={"summary": f"结果 {index}"}, db_name=database)
        continuation, created = create_join_continuation_if_ready(child_task_uid=str(child["task_uid"]), db_name=database)
        if index == 0:
            assert continuation is None and created is False
        else:
            assert continuation is not None and created is True

    duplicate, duplicate_created = create_join_continuation_if_ready(child_task_uid=str(children[-1]["task_uid"]), db_name=database)
    assert duplicate is not None and duplicate_created is False
    assert duplicate["kind"] == AgentTaskKind.CONTINUATION.value
    assert duplicate["input"]["parent_task_uid"] == leader["task_uid"]
    assert [item["tool_call_id"] for item in duplicate["input"]["tool_results"]] == ["call-0", "call-1"]

    leased_continuation = claim_task_by_uid(task_uid=str(duplicate["task_uid"]), worker_id="continuation", db_name=database)
    assert leased_continuation is not None
    assert complete_task_attempt(task_uid=str(duplicate["task_uid"]), attempt_uid=leased_continuation["current_attempt_uid"], result={"summary": "已整合"}, db_name=database)
    assert reconcile_completed_continuation_parents(db_name=database) == [leader["task_uid"]]
    assert get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)["status"] == "completed"


def test_addressed_claim_leases_only_the_requested_task_once(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    run_uid = _run_uid(database)
    first, _ = create_agent_task(
        run_uid=run_uid, kind=AgentTaskKind.LEADER, idempotency_key="leader", db_name=database
    )
    second, _ = create_agent_task(
        run_uid=run_uid, kind=AgentTaskKind.SUBAGENT, idempotency_key="other", db_name=database
    )

    claimed = claim_task_by_uid(task_uid=first["task_uid"], worker_id="worker-a", db_name=database)
    duplicate = claim_task_by_uid(task_uid=first["task_uid"], worker_id="worker-b", db_name=database)

    assert claimed is not None
    assert claimed["task_uid"] == first["task_uid"]
    assert duplicate is None
    assert get_agent_task(task_uid=second["task_uid"], db_name=database)["status"] == "queued"


def test_concurrent_worker_claims_and_events_preserve_one_owner_and_event_order(tmp_path: Path) -> None:
    """SQLite desktop workers serialize writes exactly as deployed worker processes do."""
    database = str(tmp_path / "concurrent-worker.sqlite")
    run_uid = _run_uid(database)
    task, _ = create_agent_task(
        run_uid=run_uid,
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key="single-owner",
        db_name=database,
    )
    barrier = Barrier(3)
    claimed: list[dict[str, object] | None] = []
    events: list[dict[str, object]] = []
    guard = Lock()

    def claim(worker_id: str) -> None:
        barrier.wait()
        result = claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id=worker_id, db_name=database)
        with guard:
            claimed.append(result)

    def append_event() -> None:
        barrier.wait()
        result = append_run_event(
            run_uid=run_uid,
            event_type="worker.observed",
            payload={"source": "concurrent-test"},
            db_name=database,
        )
        with guard:
            events.append(result)

    threads = [Thread(target=claim, args=("worker-a",)), Thread(target=claim, args=("worker-b",)), Thread(target=append_event)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(result is not None for result in claimed) == 1
    replay = list_run_events(run_uid=run_uid, db_name=database)
    assert [event["sequence"] for event in replay] == list(range(1, len(replay) + 1))
    assert len(events) == 1


def test_queued_task_cancellation_is_terminal_and_not_claimed(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    task, _ = create_agent_task(
        run_uid=_run_uid(database),
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key="cancel-me",
        db_name=database,
    )

    assert request_task_cancel(task_uid=task["task_uid"], db_name=database)
    assert claim_next_task(worker_id="worker-a", db_name=database) is None
    persisted = get_agent_task(task_uid=task["task_uid"], db_name=database)
    assert persisted is not None
    assert persisted["status"] == AgentTaskStatus.CANCELLED.value


def test_active_task_cancellation_wins_at_the_worker_safe_boundary(tmp_path: Path) -> None:
    database = str(tmp_path / "active-cancel.sqlite")
    task, _ = create_agent_task(
        run_uid=_run_uid(database),
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key="active-cancel",
        db_name=database,
    )
    claimed = claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id="worker", db_name=database)
    assert claimed is not None
    assert mark_task_running(
        task_uid=str(task["task_uid"]),
        attempt_uid=str(claimed["current_attempt_uid"]),
        db_name=database,
    )
    assert request_task_cancel(task_uid=str(task["task_uid"]), db_name=database)

    assert complete_task_attempt(
        task_uid=str(task["task_uid"]),
        attempt_uid=str(claimed["current_attempt_uid"]),
        result={"summary": "late result"},
        db_name=database,
    )

    persisted = get_agent_task(task_uid=str(task["task_uid"]), db_name=database)
    attempts = list_agent_task_attempts(task_uid=str(task["task_uid"]), db_name=database)
    assert persisted is not None and persisted["status"] == AgentTaskStatus.CANCELLED.value
    assert persisted["result"] == {}
    assert attempts[-1]["status"] == AgentTaskAttemptStatus.CANCELLED.value


def test_run_cancellation_marks_queued_and_active_tasks_for_safe_stop(tmp_path: Path) -> None:
    database = str(tmp_path / "run-cancel.sqlite")
    run_uid = _run_uid(database)
    queued, _ = create_agent_task(
        run_uid=run_uid, kind=AgentTaskKind.SUBAGENT, idempotency_key="queued", db_name=database
    )
    active, _ = create_agent_task(
        run_uid=run_uid, kind=AgentTaskKind.SUBAGENT, idempotency_key="active", db_name=database
    )
    claimed = claim_task_by_uid(task_uid=str(active["task_uid"]), worker_id="worker", db_name=database)
    assert claimed is not None
    assert mark_task_running(
        task_uid=str(active["task_uid"]),
        attempt_uid=str(claimed["current_attempt_uid"]),
        db_name=database,
    )

    assert request_run_cancel(run_uid=run_uid, db_name=database)

    cancelled_queued = get_agent_task(task_uid=str(queued["task_uid"]), db_name=database)
    cancelling_active = get_agent_task(task_uid=str(active["task_uid"]), db_name=database)
    assert cancelled_queued is not None and cancelled_queued["status"] == "cancelled"
    assert cancelling_active is not None and cancelling_active["status"] == "running"
    assert cancelling_active["cancel_requested_at"]
    assert not request_run_cancel(run_uid=run_uid, db_name=database)


def test_retry_creates_a_new_task_without_rewriting_failed_history(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    task, _ = create_agent_task(
        run_uid=_run_uid(database), kind=AgentTaskKind.SUBAGENT, idempotency_key="retry", db_name=database
    )
    claimed = claim_next_task(worker_id="worker", db_name=database)
    assert claimed is not None
    assert complete_task_attempt(
        task_uid=task["task_uid"], attempt_uid=claimed["current_attempt_uid"], error_message="网络错误", db_name=database
    )

    retried = retry_agent_task(task_uid=task["task_uid"], db_name=database)

    assert retried["task_uid"] != task["task_uid"]
    assert retried["status"] == "queued"
    original = get_agent_task(task_uid=task["task_uid"], db_name=database)
    assert original is not None
    assert original["status"] == "failed"


def test_run_item_event_updates_projection_in_the_same_log_sequence(tmp_path: Path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    run_uid = _run_uid(database)

    started = append_run_item_event(
        run_uid=run_uid,
        item_uid="item-task-1",
        item_type="agent_task",
        task_uid="task-1",
        status="in_progress",
        event_type="item.created",
        payload={"summary": "正在核验方法"},
        db_name=database,
    )
    completed = append_run_item_event(
        run_uid=run_uid,
        item_uid="item-task-1",
        item_type="agent_task",
        task_uid="task-1",
        status="completed",
        event_type="item.completed",
        payload={"summary": "已核验方法"},
        db_name=database,
    )

    assert started["version"] == 2
    assert completed["sequence"] == started["sequence"] + 1
    items = list_run_items(run_uid=run_uid, db_name=database)
    assert len(items) == 1
    assert items[0]["id"] == "item-task-1"
    assert items[0]["taskId"] == "task-1"
    assert items[0]["type"] == "agent_task"
    assert items[0]["status"] == "completed"
    assert items[0]["payload"] == {"summary": "已核验方法"}
    assert items[0]["createdAt"]
    assert items[0]["updatedAt"]
    event = list_run_events(run_uid=run_uid, db_name=database)[-1]
    assert event["version"] == 2
    assert event["payload"] == {}
    assert event["item"] == {
        "id": "item-task-1",
        "type": "agent_task",
        "status": "completed",
        "taskId": "task-1",
        "payload": {"summary": "已核验方法"},
    }


def test_text_item_projection_accumulates_v2_deltas(tmp_path: Path) -> None:
    database = str(tmp_path / "text-items.sqlite")
    run_uid = _run_uid(database)

    append_run_item_event(
        run_uid=run_uid,
        item_uid="item_assistant_message_text-0",
        item_type="assistant_message",
        status="in_progress",
        event_type="item.delta",
        payload={"partId": "text-0", "delta": "第一段"},
        db_name=database,
    )
    append_run_item_event(
        run_uid=run_uid,
        item_uid="item_assistant_message_text-0",
        item_type="assistant_message",
        status="completed",
        event_type="item.delta",
        payload={"partId": "text-0", "delta": "第二段"},
        db_name=database,
    )

    item = list_run_items(run_uid=run_uid, db_name=database)[0]
    assert item["payload"]["text"] == "第一段第二段"
    assert item["payload"]["delta"] == "第二段"
