"""Tiered evidence injection (P2): preview-first search results.

search_document normally embeds each evidence chunk's full text in the tool
result. With AGENT_EVIDENCE_TIERED=1 the payload carries short previews plus
a read_evidence tool for on-demand full text - weaker models regress when a
single tool result carries several full chunks (matrix data: M2.5 rich
evidence 7->4). The cache lives in tool closure state, so it is per-session
(production) or per-case (live eval harness) by construction.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Preview budget for tiered evidence; full text stays reachable via
# read_evidence. Env: AGENT_EVIDENCE_PREVIEW_CHARS.
DEFAULT_EVIDENCE_PREVIEW_CHARS = 160
EVIDENCE_TIERING_HINT = (
    "[证据分层] 以上为证据预览;关键论断需要全文时,调用 read_evidence(chunk_id) 获取完整原文。"
)


def evidence_tiering_enabled() -> bool:
    return os.getenv("AGENT_EVIDENCE_TIERED", "0").strip().lower() in {"1", "true", "on"}


def preview_chars() -> int:
    raw = os.getenv("AGENT_EVIDENCE_PREVIEW_CHARS", str(DEFAULT_EVIDENCE_PREVIEW_CHARS))
    try:
        return max(40, int(raw))
    except ValueError:
        return DEFAULT_EVIDENCE_PREVIEW_CHARS


class ReadEvidenceInput(BaseModel):
    chunk_id: str = Field(description="chunk_id from a search_document evidence item")


def shape_evidence_payload_for_preview(
    payload: Any,
    *,
    budget: int,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (preview payload, chunk_id -> full text) without mutating input.

    Citation-bearing fields are untouched; only `text` is shortened. The hint
    rides the payload so the model learns the expansion path from the result
    itself.
    """
    if not isinstance(payload, dict):
        return {}, {}
    preview: dict[str, Any] = dict(payload)
    full_texts: dict[str, str] = {}
    evidences = preview.get("evidences")
    if isinstance(evidences, list):
        shaped: list[Any] = []
        for item in evidences:
            if not isinstance(item, dict):
                shaped.append(item)
                continue
            text = str(item.get("text") or "")
            chunk_id = str(item.get("chunk_id") or "").strip()
            if chunk_id and len(text) > budget:
                full_texts[chunk_id] = text
                shaped.append({**item, "text": text[:budget] + "…", "truncated": True})
            else:
                shaped.append(item)
        preview["evidences"] = shaped
    if full_texts:
        preview["tiering_hint"] = EVIDENCE_TIERING_HINT
    return preview, full_texts


def build_read_evidence_tool(cache: dict[str, str]) -> Callable[..., Any]:
    @tool(
        "read_evidence",
        description=(
            "Read the full text of one evidence chunk from the current session's "
            "search results. Pass the chunk_id exactly as it appeared in the "
            "search_document evidence item."
        ),
        args_schema=ReadEvidenceInput,
    )
    def read_evidence(chunk_id: str) -> str:
        text = cache.get(chunk_id.strip())
        if text is None:
            known = min(len(cache), 5)
            return (
                f"No cached evidence chunk '{chunk_id}'. Chunks are cacheable only "
                "after a tiered search_document result truncated them; re-run the "
                f"search first. ({known} cached)"
            )
        return text

    return read_evidence


__all__ = [
    "DEFAULT_EVIDENCE_PREVIEW_CHARS",
    "build_read_evidence_tool",
    "evidence_tiering_enabled",
    "preview_chars",
    "shape_evidence_payload_for_preview",
]
