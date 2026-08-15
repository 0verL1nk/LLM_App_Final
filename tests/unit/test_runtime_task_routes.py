from fastapi.testclient import TestClient

from agent.adapters.orm.task_attempt_repository import claim_next_task
from agent.adapters.orm.task_dispatch_repository import create_leader_run
from api.main import app


def test_task_route_returns_owned_task_with_attempts(monkeypatch, tmp_path) -> None:
    database = str(tmp_path / "tasks.sqlite")
    run, _, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="问题",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "问题"},
        db_name=database,
    )
    task = claim_next_task(worker_id="worker-1", db_name=database)
    assert task is not None

    from api import runtime_task_routes

    original_get_task = runtime_task_routes.get_agent_task
    original_attempts = runtime_task_routes.list_agent_task_attempts
    original_get_run = runtime_task_routes.get_run
    monkeypatch.setattr(
        runtime_task_routes,
        "get_agent_task",
        lambda *, task_uid: original_get_task(task_uid=task_uid, db_name=database),
    )
    monkeypatch.setattr(
        runtime_task_routes,
        "list_agent_task_attempts",
        lambda *, task_uid: original_attempts(task_uid=task_uid, db_name=database),
    )
    monkeypatch.setattr(
        runtime_task_routes,
        "get_run",
        lambda *, run_uid, user_uuid: original_get_run(run_uid=run_uid, user_uuid=user_uuid, db_name=database),
    )

    client = TestClient(app)
    response = client.get(f"/api/v1/tasks/{task['task_uid']}", headers={"X-User-Id": "user-1"})
    forbidden = client.get(f"/api/v1/tasks/{task['task_uid']}", headers={"X-User-Id": "user-2"})

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["task_uid"] == task["task_uid"]
    assert detail["run_uid"] == run["run_uid"]
    assert [attempt["attempt_number"] for attempt in detail["attempts"]] == [1]
    assert detail["attempts"][0]["worker_id"] == "worker-1"
    assert forbidden.status_code == 404
