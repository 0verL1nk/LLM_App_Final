from fastapi.testclient import TestClient

from api.main import app


def test_context_memory_routes_require_project_and_scope_writes(monkeypatch) -> None:
    from api import context_memory_routes as routes

    monkeypatch.setattr(routes, "require_project", lambda **_kwargs: {"uid": "project"})
    monkeypatch.setattr(routes, "list_memory_items", lambda **_kwargs: [{"memory_uid": "m1"}])
    monkeypatch.setattr(routes, "upsert_memory_item", lambda **_kwargs: "m2")
    monkeypatch.setattr(routes, "update_memory_item", lambda **_kwargs: True)
    monkeypatch.setattr(routes, "delete_memory_item", lambda **_kwargs: True)
    client = TestClient(app)
    headers = {"X-User-Id": "user"}

    listed = client.get("/api/v1/projects/project/memory/L3", headers=headers)
    created = client.post(
        "/api/v1/projects/project/memory/L4", headers=headers,
        json={"content": "prefer concise", "memory_type": "preference"},
    )
    edited = client.patch(
        "/api/v1/projects/project/memory/L4/m2", headers=headers,
        json={"content": "prefer concise", "memory_type": "preference"},
    )
    deleted = client.delete("/api/v1/projects/project/memory/L4/m2", headers=headers)

    assert listed.json()["data"] == [{"memory_uid": "m1"}]
    assert created.json()["data"]["memory_uid"] == "m2"
    assert edited.status_code == 200
    assert deleted.status_code == 204
