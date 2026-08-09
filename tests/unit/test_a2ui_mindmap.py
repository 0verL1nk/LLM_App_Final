from agent.application.a2ui_mindmap import (
    build_mindmap_surface_from_request,
    parse_a2ui_mindmap_jsonl,
)


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


def test_late_evidence_enriches_the_existing_surface_identity() -> None:
    request = {"title": "论文结构", "root": {"label": "论文", "children": [], "citation_ids": ["chunk-1"]}}
    provisional = build_mindmap_surface_from_request(request, allowed_citation_ids=set())
    enriched = build_mindmap_surface_from_request(request, allowed_citation_ids={"chunk-1"})

    assert provisional is not None and enriched is not None
    assert provisional["surfaceId"] == enriched["surfaceId"]
    assert "citation_ids" not in provisional["mindmap"]
    assert enriched["mindmap"]["citation_ids"] == ["chunk-1"]


def test_builds_tool_requested_surface_and_keeps_only_retrieved_citations() -> None:
    surface = build_mindmap_surface_from_request(
        {
            "title": "方法脉络",
            "root": {
                "label": "论文",
                "citation_ids": ["chunk-1", "invented"],
                "children": [{"label": "方法", "citation_ids": ["chunk-2"], "children": []}],
            },
        },
        allowed_citation_ids={"chunk-1", "chunk-2"},
    )

    assert surface is not None
    assert surface["title"] == "方法脉络"
    assert surface["mindmap"]["citation_ids"] == ["chunk-1"]
    assert surface["mindmap"]["children"][0]["citation_ids"] == ["chunk-2"]
    assert len(surface["messages"]) == 3
