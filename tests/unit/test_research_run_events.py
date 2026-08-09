from typing import Any

from agent.application import research_workspace


def test_research_run_emits_validated_surface_metadata(monkeypatch) -> None:
    events: list[dict[str, Any]] = []

    monkeypatch.setattr(research_workspace, "update_run_status", lambda **_kwargs: True)
    monkeypatch.setattr(
        research_workspace,
        "append_run_event",
        lambda **kwargs: events.append(kwargs) or kwargs,
    )
    monkeypatch.setattr(
        research_workspace.research_workspace_service,
        "execute_turn",
        lambda **_kwargs: {
            "a2ui_surface": {
                "catalogId": "https://papersage.local/a2ui/catalogs/mindmap-v1.json",
                "surfaceId": "research-map-1",
                "title": "论文结构",
                "messages": [{"version": "v0.9", "createSurface": {"surfaceId": "research-map-1"}}],
            }
        },
    )

    research_workspace.execute_research_run(
        run_uid="run-1",
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        prompt="梳理结构",
    )

    a2ui_event = next(event for event in events if event["event_type"] == "ui.a2ui")
    assert a2ui_event["payload"] == {
        "envelope": {"version": "v0.9", "createSurface": {"surfaceId": "research-map-1"}},
        "surface": {
            "catalogId": "https://papersage.local/a2ui/catalogs/mindmap-v1.json",
            "surfaceId": "research-map-1",
            "title": "论文结构",
        },
    }
