"""Build one serializable project-document index artifact."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


def build_project_doc_index_artifact(
    *, project_uid: str, doc_uid: str, doc_name: str, normalized_text: str,
    source_spans: list[dict[str, Any]] | None, settings_signature: str, text_hash: str,
    splitter: Any, embeddings: Any, chunk_documents: list[Any] | None = None,
    schema_version: int = 3, normalize_vectors: Callable[[Any], list[list[float]]] | None = None,
    progress_callback: Callable[[str, int | None, int | None], None] | None = None,
) -> dict[str, Any]:
    """Chunk, preserve source coordinates, and embed a complete document payload."""
    documents = chunk_documents or splitter.create_documents(
        [normalized_text], metadatas=[{"doc_uid": doc_uid, "doc_name": doc_name, "project_uid": project_uid}],
    )
    for document in documents:
        document.metadata.setdefault("doc_uid", doc_uid)
        document.metadata.setdefault("doc_name", doc_name)
        document.metadata.setdefault("project_uid", project_uid)
    chunks = [document.page_content for document in documents]
    if progress_callback is not None:
        progress_callback("chunking", len(chunks), len(chunks))
    metadatas = [dict(document.metadata) if isinstance(document.metadata, dict) else {} for document in documents]
    for document, metadata in zip(documents, metadatas, strict=True):
        start_index = metadata.get("start_index")
        if not isinstance(start_index, int):
            continue
        end_index = start_index + len(document.page_content)
        locations = [span for span in source_spans or [] if isinstance(span.get("start"), int) and isinstance(span.get("end"), int) and int(span["start"]) < end_index and int(span["end"]) > start_index]
        if locations:
            metadata["ocr_locations"] = locations
            if isinstance(locations[0].get("page_no"), int):
                metadata["page_no"] = locations[0]["page_no"]
    vectors: list[list[float]] = []
    batch_size = max(1, int(os.getenv("RAG_INDEX_BATCH_SIZE", "256")))
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors.extend((normalize_vectors or _plain_vectors)(embeddings.embed_documents(batch)))
        if progress_callback is not None:
            progress_callback("embedding", min(start + len(batch), len(chunks)), len(chunks))
    return {"schema_version": schema_version, "project_uid": project_uid, "doc_uid": doc_uid, "doc_name": doc_name, "text_hash": text_hash, "settings_signature": settings_signature, "chunks": chunks, "metadatas": metadatas, "embeddings": vectors}


def _plain_vectors(values: Any) -> list[list[float]]:
    return [list(map(float, value)) for value in values if isinstance(value, (list, tuple))]
