"""Format-aware chunks for the persisted project RAG index."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from .chunking import SemanticAwareSplitter


def markdown_documents(*, text: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    """Preserve only headings emitted by the document parser as chunk metadata."""
    chunks = SemanticAwareSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ).split_markdown(text)
    documents: list[Document] = []
    cursor = 0
    for chunk in chunks:
        start_index = text.find(chunk.content, cursor)
        if start_index < 0:
            raise ValueError("Markdown chunk is not traceable to parser output")
        cursor = start_index + len(chunk.content)
        metadata: dict[str, Any] = {
            "start_index": start_index,
            "section_path": chunk.metadata.section_path,
            "heading_level": chunk.metadata.heading_level,
            "prev_chunk_id": chunk.metadata.prev_chunk_id,
            "next_chunk_id": chunk.metadata.next_chunk_id,
        }
        documents.append(Document(page_content=chunk.content, metadata=metadata))
    return documents


__all__ = ["markdown_documents"]
