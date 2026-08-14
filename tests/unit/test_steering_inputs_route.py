from fastapi.testclient import TestClient

from api.main import app


def test_steering_input_route_returns_conflict_when_no_run_is_active(monkeypatch) -> None:
    from api import routes

    monkeypatch.setattr(
        routes.research_workspace_service,
        "queue_steering_input",
        lambda **_kwargs: (_ for _ in ()).throw(LookupError("No running Run accepts steering input")),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/project-1/sessions/session-1/steering-inputs",
        headers={"X-User-Id": "user-1"},
        json={"prompt": "继续核验", "client_request_id": "follow-up-001"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "No running Run accepts steering input"


def test_steering_input_route_returns_the_durable_queue_identity(monkeypatch) -> None:
    from api import routes

    monkeypatch.setattr(
        routes.research_workspace_service,
        "queue_steering_input",
        lambda **_kwargs: {"input_uid": "input-1", "run_uid": "run-1", "status": "queued"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/project-1/sessions/session-1/steering-inputs",
        headers={"X-User-Id": "user-1"},
        json={"prompt": "继续核验", "client_request_id": "follow-up-001"},
    )

    assert response.status_code == 202
    assert response.json()["data"] == {"input_id": "input-1", "run_id": "run-1", "status": "queued"}
