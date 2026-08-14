import sqlite3
from pathlib import Path

from agent.adapters.orm.run_repository import (
    append_run_event,
    claim_run_execution,
    create_run,
    expire_stalled_runs,
    get_run,
    list_run_events,
    list_session_runs,
    update_run_status,
)


def test_run_creation_is_idempotent_and_events_are_ordered(tmp_path: Path) -> None:
    database = str(tmp_path / "runs.sqlite")
    first, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-123",
        prompt="研究这个问题",
        db_name=database,
    )
    duplicate, duplicate_created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-123",
        prompt="研究这个问题",
        db_name=database,
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["run_uid"] == first["run_uid"]

    run_uid = str(first["run_uid"])
    append_run_event(
        run_uid=run_uid,
        event_type="run.started",
        payload={"status": "running"},
        db_name=database,
    )
    append_run_event(
        run_uid=run_uid,
        event_type="step.progress",
        payload={"trace": {"content": "检索文档"}},
        db_name=database,
    )
    update_run_status(run_uid=run_uid, status="completed", db_name=database)

    events = list_run_events(run_uid=run_uid, after_sequence=1, db_name=database)
    assert [event["sequence"] for event in events] == [2, 3]
    assert [event["eventType"] for event in events] == ["run.started", "step.progress"]
    assert len({event["eventId"] for event in events}) == 2
    assert get_run(run_uid=run_uid, user_uuid="user-1", db_name=database)["status"] == "completed"
    assert get_run(run_uid=run_uid, user_uuid="another-user", db_name=database) is None
    assert list_session_runs(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        db_name=database,
    ) == []


def test_list_session_runs_only_returns_resumable_owned_runs(tmp_path: Path) -> None:
    database = str(tmp_path / "runs.sqlite")
    resumable, _ = create_run(project_uid="project-1", session_uid="session-1", user_uuid="user-1", client_request_id="request-001", prompt="继续", db_name=database)
    completed, _ = create_run(project_uid="project-1", session_uid="session-1", user_uuid="user-1", client_request_id="request-002", prompt="完成", db_name=database)
    create_run(project_uid="project-1", session_uid="session-1", user_uuid="user-2", client_request_id="request-003", prompt="别人的", db_name=database)
    update_run_status(run_uid=str(completed["run_uid"]), status="completed", db_name=database)

    runs = list_session_runs(project_uid="project-1", session_uid="session-1", user_uuid="user-1", db_name=database)

    assert [run["run_uid"] for run in runs] == [resumable["run_uid"]]


def test_run_execution_can_only_be_claimed_once(tmp_path: Path) -> None:
    database = str(tmp_path / "runs.sqlite")
    run, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-claim",
        prompt="执行一次",
        db_name=database,
    )

    assert claim_run_execution(run_uid=str(run["run_uid"]), db_name=database) is True
    assert claim_run_execution(run_uid=str(run["run_uid"]), db_name=database) is False
    persisted = get_run(run_uid=str(run["run_uid"]), user_uuid="user-1", db_name=database)
    assert persisted is not None
    assert persisted["status"] == "running"


def test_stalled_run_is_failed_and_gets_a_terminal_event(tmp_path: Path) -> None:
    database = str(tmp_path / "runs.sqlite")
    run, _ = create_run(project_uid="project-1", session_uid="session-1", user_uuid="user-1", client_request_id="request-1", prompt="问题", db_name=database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE agent_runs SET updated_at = '2000-01-01T00:00:00+00:00' WHERE run_uid = ?", (run["run_uid"],))
    assert expire_stalled_runs(project_uid="project-1", session_uid="session-1", user_uuid="user-1", max_idle_seconds=0, db_name=database) == [run["run_uid"]]
    assert get_run(run_uid=run["run_uid"], user_uuid="user-1", db_name=database)["status"] == "failed"
    assert list_run_events(run_uid=run["run_uid"], db_name=database)[-1]["eventType"] == "run.failed"
    claim_run_execution,
