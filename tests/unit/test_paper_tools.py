from typing import Any

import httpx
import pytest

from agent.capabilities import build_capability_tools
from agent.scholarly_search import ScholarlySearchError, download_paper_pdf, fetch_semantic_scholar_citations
from agent.subagent.loader import load_subagent_definitions
from agent.tools import paper_library
from agent.tools.paper_library import build_add_paper_to_library_tool, get_paper_citations


class _Deps:
    project_uid = "proj-1"
    user_uuid = "user-1"


def test_paper_pack_registers_three_tools_with_bound_library_target() -> None:
    tools = build_capability_tools(["paper_pack"], _Deps())
    names = sorted(tool.name for tool in tools)
    assert names == ["add_paper_to_library", "get_paper_citations", "search_papers"]
    library_tool = next(tool for tool in tools if tool.name == "add_paper_to_library")
    fields = sorted(library_tool.tool_call_schema.model_json_schema()["properties"].keys())
    assert fields == ["title", "url"]


def test_paper_pack_without_project_context_skips_library_ingestion() -> None:
    class _BareDeps:
        project_uid = None
        user_uuid = None

    names = sorted(tool.name for tool in build_capability_tools(["paper_pack"], _BareDeps()))
    assert "add_paper_to_library" not in names


def test_builtin_subagent_definitions_load_with_paper_capability() -> None:
    definitions = {definition.name: definition for definition in load_subagent_definitions()}
    assert set(definitions) == {"researcher", "reviewer", "writer"}
    assert "paper_pack" in definitions["researcher"].capability_ids
    for definition in definitions.values():
        assert len(definition.system_prompt) > 200


def test_get_paper_citations_rejects_unknown_direction() -> None:
    assert "Direction must be" in get_paper_citations.invoke(
        {"paper_id": "abc", "direction": "sideways", "limit": 5}
    )


def test_get_paper_citations_formats_neighbours(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_fetch(paper_id: str, *, direction: str, limit: int) -> list[dict[str, Any]]:
        captured.update(paper_id=paper_id, direction=direction, limit=limit)
        return [{"title": "Citing Paper", "authors": ["A"], "year": 2025, "url": "https://x", "paper_id": "p2"}]

    monkeypatch.setattr(paper_library, "fetch_semantic_scholar_citations", fake_fetch)
    output = get_paper_citations.invoke({"paper_id": "p1", "direction": "citations", "limit": 7})
    assert "Citing Paper" in output and "p2" in output
    assert captured == {"paper_id": "p1", "direction": "citations", "limit": 7}


def test_add_paper_to_library_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paper_library, "download_paper_pdf", lambda url: b"%PDF-1.4 fake")
    uploaded: dict[str, Any] = {}

    def fake_upload(**kwargs: Any) -> dict[str, Any]:
        uploaded.update(kwargs)
        return {"uid": "doc-9", "file_name": "Attention Is All You Need.pdf"}

    monkeypatch.setattr("agent.application.document_library.upload_project_document", fake_upload)
    tool = build_add_paper_to_library_tool(project_uid="proj-1", user_uuid="user-1")
    command = tool.func(
        url="https://arxiv.org/pdf/1706.03762",
        title="Attention Is All You Need",
        tool_call_id="call-1",
        state={},
    )
    message = command.update["messages"][0]
    assert message.tool_call_id == "call-1"
    assert "doc-9" in message.content
    assert uploaded["project_uid"] == "proj-1" and uploaded["user_uuid"] == "user-1"
    assert uploaded["file_name"].endswith(".pdf")


def test_add_paper_to_library_reports_download_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(url: str) -> bytes:
        raise ScholarlySearchError("Downloaded content is not a PDF (missing %PDF header).")

    monkeypatch.setattr(paper_library, "download_paper_pdf", fake_download)
    tool = build_add_paper_to_library_tool(project_uid="proj-1", user_uuid="user-1")
    command = tool.func(url="https://example.com/not-a-pdf", title="T", tool_call_id="call-2", state={})
    message = command.update["messages"][0]
    assert message.status == "error"
    assert "not a PDF" in message.content


def test_fetch_citations_parses_nested_graph_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": [
            {"citingPaper": {"paperId": "c1", "title": "New Work", "authors": [{"name": "B"}], "year": 2026}},
            {"citingPaper": {"paperId": None, "title": None}},
            "junk",
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "paper/search" not in str(request.url)
        return httpx.Response(200, json=payload)

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **{k: v for k, v in kwargs.items() if k != "timeout"} | {"timeout": 5}),
    )
    papers = fetch_semantic_scholar_citations("seed", direction="citations", limit=5)
    assert [paper["title"] for paper in papers] == ["New Work"]


def test_download_paper_pdf_rejects_non_http_and_non_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ScholarlySearchError, match="http"):
        download_paper_pdf("ftp://example.com/paper.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not a pdf</html>")

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **{k: v for k, v in kwargs.items() if k != "timeout"} | {"timeout": 5}),
    )
    with pytest.raises(ScholarlySearchError, match="not a PDF"):
        download_paper_pdf("https://example.com/paper.pdf")
