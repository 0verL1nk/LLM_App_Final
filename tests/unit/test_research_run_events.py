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


def test_research_run_anchors_surface_between_streamed_markdown_parts(monkeypatch) -> None:
    events: list[dict[str, Any]] = []
    surface = {
        "catalogId": "https://papersage.local/a2ui/catalogs/mindmap-v1.json",
        "surfaceId": "research-map-1",
        "title": "论文结构",
        "messages": [
            {"version": "v0.9", "createSurface": {"surfaceId": "research-map-1"}},
            {"version": "v0.9", "updateDataModel": {"surfaceId": "research-map-1", "path": "/mindmap", "value": {"label": "论文", "children": []}}},
        ],
    }
    monkeypatch.setattr(research_workspace, "update_run_status", lambda **_kwargs: True)
    monkeypatch.setattr(research_workspace, "append_run_event", lambda **kwargs: events.append(kwargs) or kwargs)

    def execute_turn(**kwargs: Any) -> dict[str, Any]:
        on_event = kwargs["on_event"]
        on_event({"performative": "answer_part_delta", "content": "前文", "metadata": {"part_id": "text-0"}})
        on_event({"performative": "answer_part_insert", "metadata": {"part_id": "surface-0", "part_type": "a2ui"}})
        on_event({"performative": "a2ui_surface_ready", "metadata": {"part_id": "surface-0", "surface": surface}})
        on_event({"performative": "answer_part_delta", "content": "后文", "metadata": {"part_id": "text-1"}})
        return {"a2ui_surfaces": [{**surface, "partId": "surface-0"}]}

    monkeypatch.setattr(research_workspace.research_workspace_service, "execute_turn", execute_turn)

    research_workspace.execute_research_run(run_uid="run-1", project_uid="project-1", session_uid="session-1", user_uuid="user-1", prompt="梳理结构")

    public_events = [event for event in events if event["event_type"] not in {"run.started", "run.completed"}]
    assert [event["event_type"] for event in public_events] == ["message.part.delta", "message.part.insert", "ui.a2ui", "ui.a2ui", "message.part.delta", "ui.a2ui"]
    assert public_events[1]["payload"] == {"partId": "surface-0", "type": "a2ui"}
    assert public_events[2]["payload"]["surface"]["partId"] == "surface-0"
