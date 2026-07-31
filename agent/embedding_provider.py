"""Local semantic embedding model provider."""

from functools import lru_cache

from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

from .settings import load_agent_settings


@lru_cache(maxsize=2)
def get_embedding_model() -> FastEmbedEmbeddings:
    settings = load_agent_settings()
    return FastEmbedEmbeddings(
        model_name=settings.local_embedding_model,
        cache_dir=settings.local_embedding_cache_dir,
    )


__all__ = ["get_embedding_model"]
