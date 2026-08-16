"""Slash command route tests (GET /skills, POST session commands)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def _client(monkeypatch, *, catalog=None, execute=None) -> TestClient:
    from api import session_command_routes as routes

    monkeypatch.setattr(routes, "list_skill_catalog", lambda: catalog or [])
    monkeypatch.setattr(routes, "execute_session_command", execute or (lambda **_kwargs: {}))
    return TestClient(app)


def test_skills_endpoint_returns_catalog_envelope(monkeypatch) -> None:
    client = _client(monkeypatch, catalog=[{"name": "summary", "description": "总结"}])

    response = client.get("/api/v1/skills", headers={"X-User-Id": "user"})

    assert response.status_code == 200
    assert response.json()["data"] == [{"name": "summary", "description": "总结"}]


def test_session_command_endpoint_returns_persisted_message(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _execute(**kwargs):
        captured.update(kwargs)
        return {"message": {"role": "assistant", "content": "ok"}, "stats": None}

    client = _client(monkeypatch, execute=_execute)

    response = client.post(
        "/api/v1/projects/p1/sessions/s1/commands",
        headers={"X-User-Id": "user"},
        json={"command": "skills", "args": ""},
    )

    assert response.status_code == 200
    assert response.json()["data"]["message"]["content"] == "ok"
    assert captured["command"] == "skills"
    assert captured["project_uid"] == "p1"


def test_session_command_endpoint_maps_domain_errors(monkeypatch) -> None:
    from api.session_command_routes import SessionCommandConflict, SessionCommandError

    scenarios = [
        (SessionCommandError("未知命令：/foobar"), 400),
        (SessionCommandConflict("有进行中的研究运行"), 409),
        (LookupError("Session not found"), 404),
    ]
    headers = {"X-User-Id": "user"}
    for exc, expected_status in scenarios:
        def _raise(_exc=exc, **_kwargs):
            raise _exc

        client = _client(monkeypatch, execute=_raise)
        response = client.post(
            "/api/v1/projects/p1/sessions/s1/commands", headers=headers, json={"command": "compact"}
        )
        assert response.status_code == expected_status


def test_session_command_endpoint_rejects_empty_body(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/api/v1/projects/p1/sessions/s1/commands",
        headers={"X-User-Id": "user"},
        json={"command": ""},
    )

    assert response.status_code == 422
