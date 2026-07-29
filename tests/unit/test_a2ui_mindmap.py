from agent.application.a2ui_mindmap import parse_a2ui_mindmap_jsonl


def test_parses_only_the_restricted_mindmap_catalog() -> None:
    surface = parse_a2ui_mindmap_jsonl(
        """{"version":"v0.9","createSurface":{"surfaceId":"map-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}
{"version":"v0.9","updateComponents":{"surfaceId":"map-1","components":[{"id":"root","component":"Mindmap","data":{"path":"/mindmap"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"map-1","path":"/mindmap","value":{"label":"主题","children":[{"label":"方法","children":[]}]}}}"""
    )

    assert surface is not None
    assert surface["catalogId"] == "https://papersage.local/a2ui/catalogs/mindmap-v1.json"
    assert surface["surfaceId"] == "map-1"
    assert surface["mindmap"] == {"label": "主题", "children": [{"label": "方法", "children": []}]}
    assert len(surface["messages"]) == 3


def test_rejects_unapproved_components_and_scripts() -> None:
    assert parse_a2ui_mindmap_jsonl(
        """{"version":"v0.9","createSurface":{"surfaceId":"map-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}
{"version":"v0.9","updateComponents":{"surfaceId":"map-1","components":[{"id":"root","component":"Html","script":"alert(1)"}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"map-1","path":"/mindmap","value":{"label":"主题","children":[]}}}"""
    ) is None
