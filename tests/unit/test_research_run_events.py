from typing import Any

from agent.application import research_workspace


def _capture_v2_writes(monkeypatch) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lifecycle: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    monkeypatch.setattr(research_workspace, "update_run_status", lambda **_kwargs: True)
    monkeypatch.setattr(research_workspace, "claim_run_execution", lambda **_kwargs: True)
    monkeypatch.setattr(research_workspace, "append_run_lifecycle_event", lambda **kwargs: lifecycle.append(kwargs) or kwargs)
    monkeypatch.setattr(research_workspace, "append_run_item_event", lambda **kwargs: items.append(kwargs) or kwargs)
    return lifecycle, items


def test_research_run_emits_validated_surface_as_v2_presentation_item(monkeypatch) -> None:
    _lifecycle, items = _capture_v2_writes(monkeypatch)
    monkeypatch.setattr(
        research_workspace.research_workspace_service,
        "execute_turn",
        lambda **_kwargs: {
            "response_parts": [
                {"id": "text-0", "type": "markdown", "text": "正文"},
                {
                    "id": "component-0",
                    "type": "component",
                    "component": "research-map",
                    "state": "ready",
                    "xml": '<map title="论文结构"><node label="论文" /></map>',
                },
            ]
        },
    )

    research_workspace.execute_research_run(run_uid="run-1", project_uid="project-1", session_uid="session-1", user_uuid="user-1", prompt="梳理结构")

    component = next(item for item in items if item["item_type"] == "component")
    assert component["event_type"] == "item.completed"
    assert component["payload"] == {
        "partId": "component-0",
        "component": "research-map",
        "state": "ready",
        "xml": '<map title="论文结构"><node label="论文" /></map>',
    }


def test_research_run_uses_v2_items_for_parts_and_presentation(monkeypatch) -> None:
    lifecycle, items = _capture_v2_writes(monkeypatch)
    surface = {"catalogId": "https://papersage.local/a2ui/catalogs/mindmap-v1.json", "surfaceId": "research-map-1", "title": "论文结构", "messages": [{"version": "v0.9", "createSurface": {"surfaceId": "research-map-1"}}, {"version": "v0.9", "updateDataModel": {"surfaceId": "research-map-1", "path": "/mindmap", "value": {"label": "论文", "children": []}}}]}

    def execute_turn(**kwargs: Any) -> dict[str, Any]:
        on_event = kwargs["on_event"]
        on_event({"performative": "answer_part_delta", "content": "前文", "metadata": {"part_id": "text-0"}})
        on_event({"performative": "answer_part_insert", "metadata": {"part_id": "surface-0", "part_type": "a2ui"}})
        on_event({"performative": "a2ui_surface_ready", "metadata": {"part_id": "surface-0", "surface": surface}})
        on_event({"performative": "answer_part_delta", "content": "后文", "metadata": {"part_id": "text-1"}})
        return {"a2ui_surfaces": [{**surface, "partId": "surface-0"}]}

    monkeypatch.setattr(research_workspace.research_workspace_service, "execute_turn", execute_turn)
    research_workspace.execute_research_run(run_uid="run-1", project_uid="project-1", session_uid="session-1", user_uuid="user-1", prompt="梳理结构")

    assert [item["event_type"] for item in items] == ["item.delta", "item.created", "item.delta", "item.delta", "item.delta"]
    assert items[1]["item_type"] == "presentation"
    assert items[1]["payload"] == {"partId": "surface-0", "presentation": "a2ui"}
    assert not [event for event in lifecycle if event["event_type"].startswith("message.") or event["event_type"] == "ui.a2ui"]
