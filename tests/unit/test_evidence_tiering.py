"""Tests for tiered evidence injection (P2) and the citation audit (P3-lite)."""

import json
from types import SimpleNamespace
from typing import Any

from agent.capabilities import evidence_tiering
from agent.capabilities.document import build_document_tools


def _payload(texts: dict[str, str]) -> dict[str, Any]:
    return {
        "evidences": [
            {"chunk_id": cid, "text": text, "doc_uid": "d", "page_no": 1}
            for cid, text in texts.items()
        ],
        "trace": {"mode": "project_dense"},
    }


def test_shape_truncates_long_text_and_keeps_citation_fields() -> None:
    payload = _payload({"c1": "x" * 500, "c2": "short"})

    preview, full = evidence_tiering.shape_evidence_payload_for_preview(
        payload, budget=160
    )

    assert full == {"c1": "x" * 500}
    shaped = {item["chunk_id"]: item for item in preview["evidences"]}
    assert shaped["c1"]["text"].startswith("x" * 160)
    assert shaped["c1"]["truncated"] is True
    assert shaped["c1"]["doc_uid"] == "d" and shaped["c1"]["page_no"] == 1
    assert shaped["c2"]["text"] == "short" and "truncated" not in shaped["c2"]
    assert evidence_tiering.EVIDENCE_TIERING_HINT in preview["tiering_hint"]
    # original payload untouched
    assert _payload({"c1": "x" * 500})["evidences"][0]["text"] == "x" * 500


def test_shape_without_truncation_adds_no_hint_or_cache() -> None:
    preview, full = evidence_tiering.shape_evidence_payload_for_preview(
        _payload({"c1": "short"}), budget=160
    )

    assert full == {}
    assert "tiering_hint" not in preview


def test_document_tools_tiered_mode_wires_preview_and_read_evidence(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_EVIDENCE_TIERED", "1")
    monkeypatch.setenv("AGENT_EVIDENCE_PREVIEW_CHARS", "40")
    long_text = "L" * 300
    calls: list[str] = []

    def evidence_fn(query: str) -> dict[str, Any]:
        calls.append(query)
        return _payload({"c1": long_text})

    deps = SimpleNamespace(
        search_document_fn=lambda q: "text-mode",
        search_document_evidence_fn=evidence_fn,
    )

    tools = build_document_tools(deps)
    by_name = {t.name: t for t in tools}

    assert set(by_name) >= {"search_document", "read_evidence"}
    rendered = by_name["search_document"].invoke({"query": "q"})
    payload = json.loads(rendered)
    item = payload["evidences"][0]
    assert len(item["text"]) < 60 and item["truncated"] is True
    assert calls == ["q"]

    full = by_name["read_evidence"].invoke({"chunk_id": "c1"})
    assert full == long_text

    missing = by_name["read_evidence"].invoke({"chunk_id": "nope"})
    assert "No cached evidence chunk" in missing


def test_document_tools_default_mode_unchanged(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_EVIDENCE_TIERED", raising=False)

    deps = SimpleNamespace(
        search_document_fn=lambda q: "text",
        search_document_evidence_fn=lambda q: _payload({"c1": "x" * 500}),
    )

    tools = build_document_tools(deps)
    names = {t.name for t in tools}

    assert "read_evidence" not in names
    rendered = next(t for t in tools if t.name == "search_document").invoke({"query": "q"})
    assert len(json.loads(rendered)["evidences"][0]["text"]) == 500


def test_read_evidence_cache_is_session_scoped(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_EVIDENCE_TIERED", "1")

    def make():
        deps = SimpleNamespace(
            search_document_fn=lambda q: "t",
            search_document_evidence_fn=lambda q: _payload({"c1": "z" * 200}),
        )
        return {t.name: t for t in build_document_tools(deps)}

    first, second = make(), make()
    first["search_document"].invoke({"query": "q"})

    # second session's cache never saw session one's evidence
    assert "No cached evidence chunk" in second["read_evidence"].invoke({"chunk_id": "c1"})
    assert "z" * 200 in first["read_evidence"].invoke({"chunk_id": "c1"})
