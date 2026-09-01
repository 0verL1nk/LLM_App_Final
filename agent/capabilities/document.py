from typing import Any

from ..capabilities.evidence_tiering import (
    build_read_evidence_tool,
    evidence_tiering_enabled,
    preview_chars,
    shape_evidence_payload_for_preview,
)
from ..tools.document import (
    build_list_document_tool,
    build_read_document_tool,
    build_search_document_tool,
)


def _tiered_evidence_fn(
    search_document_evidence_fn: Any,
    cache: dict[str, str],
) -> Any:
    def wrapped(query: str) -> Any:
        payload = search_document_evidence_fn(query)
        preview, full_texts = shape_evidence_payload_for_preview(
            payload, budget=preview_chars()
        )
        cache.update(full_texts)
        return preview

    return wrapped


def build_document_tools(deps: Any) -> list[Any]:
    tools: list[Any] = []
    evidence_fn = getattr(deps, "search_document_evidence_fn", None)
    # build_document_tools runs once per agent session, so this closure cache
    # is session-scoped by construction and dies with the session's tools.
    tiered_cache: dict[str, str] = {}
    if evidence_fn is not None and evidence_tiering_enabled():
        evidence_fn = _tiered_evidence_fn(evidence_fn, tiered_cache)
    tools.append(
        build_search_document_tool(
            deps.search_document_fn,
            evidence_fn,
        )
    )
    if evidence_tiering_enabled():
        tools.append(build_read_evidence_tool(tiered_cache))
    list_documents_fn = getattr(deps, "list_documents_fn", None)
    if callable(list_documents_fn):
        tools.append(build_list_document_tool(list_documents_fn))
    read_document_fn = getattr(deps, "read_document_fn", None)
    doc_id_to_text = getattr(deps, "doc_id_to_text", None)
    default_id = getattr(deps, "doc_id_default", "")
    read_document_by_id_fn = getattr(deps, "read_document_by_id_fn", None)
    if callable(read_document_fn) or doc_id_to_text or callable(read_document_by_id_fn):
        tools.append(
            build_read_document_tool(
                read_document_fn,
                deps.search_document_fn,
                doc_id_to_text,
                default_id,
                read_document_by_id_fn,
            )
        )
    return tools
