import json

from agent.tools.document import build_read_document_tool, build_search_document_tool


def test_read_document_tool_returns_citeable_structured_evidence() -> None:
    tool = build_read_document_tool(
        read_document_fn=None,
        search_document_fn=lambda _query: "",
        read_document_by_id_fn=lambda _doc_id, _offset, _limit: ("证据正文", 100),
    )

    payload = json.loads(tool.invoke({"doc_id": "doc-1", "offset": 10, "limit": 20}))

    assert payload["evidences"][0]["chunk_id"] == "doc-1:offset_10_14"
    assert payload["evidences"][0]["citation"] == "doc-1:offset_10_14|pnull|o10-14"


def test_search_document_tool_refreshes_identical_evidence_query() -> None:
    calls = {"count": 0}

    def _search_evidence(query: str):
        calls["count"] += 1
        return {
            "evidences": [
                {"chunk_id": f"chunk-{calls['count']}", "text": f"hit:{query}", "page_no": 1}
            ]
        }

    tool = build_search_document_tool(
        search_document_fn=lambda query: f"fallback:{query}",
        search_document_evidence_fn=_search_evidence,
    )

    first = json.loads(tool.invoke({"query": "RAG"}))
    second = json.loads(tool.invoke({"query": "RAG"}))

    assert calls["count"] == 2
    assert first["evidences"][0]["chunk_id"] == "chunk-1"
    assert second["evidences"][0]["chunk_id"] == "chunk-2"



def test_search_document_tool_refreshes_identical_text_query() -> None:
    calls = {"count": 0}

    def _search_text(query: str) -> str:
        calls["count"] += 1
        return f"result:{query}:{calls['count']}"

    tool = build_search_document_tool(_search_text)

    first = tool.invoke({"query": "Self-RAG"})
    second = tool.invoke({"query": "Self-RAG"})
    third = tool.invoke({"query": "GraphRAG"})

    assert calls["count"] == 3
    assert first == "result:Self-RAG:1"
    assert second == "result:Self-RAG:2"
    assert third == "result:GraphRAG:3"


def test_search_document_tool_does_not_guess_equivalent_evidence_queries() -> None:
    calls = {"count": 0}

    def _search_evidence(query: str):
        calls["count"] += 1
        return {
            "evidences": [
                {"chunk_id": f"chunk-{calls['count']}", "text": f"hit:{query}", "page_no": 1}
            ]
        }

    tool = build_search_document_tool(
        search_document_fn=lambda query: f"fallback:{query}",
        search_document_evidence_fn=_search_evidence,
    )

    first = json.loads(tool.invoke({"query": "Self-RAG NQ 50.0"}))
    second = json.loads(tool.invoke({"query": "NQ Self-RAG 50"}))

    assert calls["count"] == 2
    assert second["evidences"][0]["chunk_id"] == "chunk-2"
    assert first["evidences"][0]["chunk_id"] == "chunk-1"


def test_search_document_tool_does_not_guess_equivalent_text_queries() -> None:
    calls = {"count": 0}

    def _search_text(query: str) -> str:
        calls["count"] += 1
        return f"result:{query}:{calls['count']}"

    tool = build_search_document_tool(_search_text)

    first = tool.invoke({"query": "latency Self-RAG"})
    second = tool.invoke({"query": "Self-RAG latency"})

    assert calls["count"] == 2
    assert first == "result:latency Self-RAG:1"
    assert second == "result:Self-RAG latency:2"


def test_search_document_tool_executes_distinct_evidence_queries() -> None:
    calls = {"count": 0}

    def _search_evidence(query: str):
        calls["count"] += 1
        return {
            "evidences": [
                {"chunk_id": f"chunk-{calls['count']}", "text": f"hit:{query}", "page_no": 1}
            ]
        }

    tool = build_search_document_tool(
        search_document_fn=lambda query: f"fallback:{query}",
        search_document_evidence_fn=_search_evidence,
    )

    first = json.loads(tool.invoke({"query": "Self-RAG NQ score"}))
    second = json.loads(tool.invoke({"query": "Self-RAG NQ result"}))

    assert calls["count"] == 2
    assert first["evidences"][0]["chunk_id"] == "chunk-1"
    assert second["evidences"][0]["chunk_id"] == "chunk-2"


def test_search_document_tool_executes_distinct_text_queries() -> None:
    calls = {"count": 0}

    def _search_text(query: str) -> str:
        calls["count"] += 1
        return f"result:{query}:{calls['count']}"

    tool = build_search_document_tool(_search_text)

    first = tool.invoke({"query": "Self-RAG NQ TQA WQ results"})
    second = tool.invoke({"query": "Self-RAG NQ TQA WQ results table"})

    assert calls["count"] == 2
    assert first == "result:Self-RAG NQ TQA WQ results:1"
    assert second == "result:Self-RAG NQ TQA WQ results table:2"


def test_search_document_tool_does_not_block_short_semantic_query() -> None:
    calls = {"count": 0}

    def _search_evidence(query: str):
        calls["count"] += 1
        return {
            "evidences": [
                {"chunk_id": f"chunk-{calls['count']}", "text": f"hit:{query}", "page_no": 1}
            ]
        }

    tool = build_search_document_tool(
        search_document_fn=lambda query: f"fallback:{query}",
        search_document_evidence_fn=_search_evidence,
    )

    result = json.loads(tool.invoke({"query": "page"}))

    assert calls["count"] == 1
    assert result["evidences"][0]["chunk_id"] == "chunk-1"
