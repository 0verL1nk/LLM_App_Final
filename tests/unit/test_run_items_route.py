from fastapi.testclient import TestClient

from agent.adapters.orm.run_repository import append_run_item_event, create_run
from api.main import app


def test_run_items_route_returns_only_owned_projection(monkeypatch, tmp_path) -> None:
    database = str(tmp_path / "api.sqlite")
    run, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="问题",
        db_name=database,
    )
    append_run_item_event(
        run_uid=run["run_uid"],
        item_uid="item-1",
        item_type="tool_call",
        status="completed",
        event_type="item.completed",
        payload={"summary": "检索完成"},
        db_name=database,
    )

    from api import routes

    original_get_run = routes.get_run
    original_list_items = routes.list_run_items
    monkeypatch.setattr(routes, "get_run", lambda **kwargs: original_get_run(**kwargs, db_name=database))
    monkeypatch.setattr(routes, "list_run_items", lambda **kwargs: original_list_items(**kwargs, db_name=database))

    client = TestClient(app)
    response = client.get(f"/api/v1/runs/{run['run_uid']}/items", headers={"X-User-Id": "user-1"})

    assert response.status_code == 200
    assert response.json()["data"][0]["payload"] == {"summary": "检索完成"}
    forbidden = client.get(f"/api/v1/runs/{run['run_uid']}/items", headers={"X-User-Id": "user-2"})
    assert forbidden.status_code == 404


def test_run_cancel_route_requires_ownership_and_emits_terminal_event(monkeypatch) -> None:
    from api import routes

    events: list[dict[str, object]] = []
    monkeypatch.setattr(
        routes,
        "get_run",
        lambda *, run_uid, user_uuid: {"run_uid": run_uid} if user_uuid == "user-1" else None,
    )
    monkeypatch.setattr(routes, "request_run_cancel", lambda *, run_uid: run_uid == "run-1")
    monkeypatch.setattr(routes, "append_run_lifecycle_event", lambda **kwargs: events.append(kwargs))
    client = TestClient(app)

    response = client.post("/api/v1/runs/run-1/cancel", headers={"X-User-Id": "user-1"})
    forbidden = client.post("/api/v1/runs/run-1/cancel", headers={"X-User-Id": "user-2"})

    assert response.status_code == 200
    assert response.json()["data"] == {"run_uid": "run-1", "cancel_requested": True}
    assert events == [{"run_uid": "run-1", "event_type": "run.cancelled", "payload": {"message": "运行已取消"}}]
    assert forbidden.status_code == 404
