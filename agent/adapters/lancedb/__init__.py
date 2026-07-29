"""LanceDB adapters for persistent project retrieval indexes."""

from .rag_index import (
    document_index_exists,
    publish_document_index,
    search_published_chunks,
)

__all__ = [
    "document_index_exists",
    "publish_document_index",
    "search_published_chunks",
]
