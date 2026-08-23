"""Local semantic embedding model provider."""

from functools import lru_cache
from typing import TYPE_CHECKING

from .settings import load_agent_settings

if TYPE_CHECKING:
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings


@lru_cache(maxsize=2)
def get_embedding_model() -> "FastEmbedEmbeddings":
    # langchain_community (and through it fastembed + onnxruntime) costs
    # seconds to import; defer it until an embedding is actually requested.
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

    settings = load_agent_settings()
    return FastEmbedEmbeddings(
        model_name=settings.local_embedding_model,
        cache_dir=settings.local_embedding_cache_dir,
    )


__all__ = ["get_embedding_model"]
