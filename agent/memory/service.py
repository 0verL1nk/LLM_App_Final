"""Semantic retrieval for consolidated long-term memories."""

from typing import Any

import numpy as np

from agent.adapters.orm.memory_repository import list_memory_items
from agent.embedding_provider import get_embedding_model


def search_project_memory_items(
    *,
    uuid: str,
    project_uid: str,
    query: str,
    limit: int = 5,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    items = [
        *list_memory_items(uuid=uuid, project_uid=project_uid, level="L3", limit=300, db_name=db_name),
        *list_memory_items(uuid=uuid, project_uid=project_uid, level="L4", limit=100, db_name=db_name),
    ]
    query_text = str(query or "").strip()
    if not items or not query_text:
        return []
    embeddings = get_embedding_model()
    texts = [f"{item['title']}\n{item['content']}" for item in items]
    query_vector = np.asarray(embeddings.embed_query(query_text), dtype=np.float32)
    memory_vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
    query_norm = np.linalg.norm(query_vector)
    memory_norms = np.linalg.norm(memory_vectors, axis=1)
    denominators = memory_norms * query_norm
    scores = np.divide(
        memory_vectors @ query_vector,
        denominators,
        out=np.zeros_like(memory_norms),
        where=denominators != 0,
    )
    ranked_indices = np.argsort(scores)[::-1][: max(1, int(limit))]
    selected: list[dict[str, Any]] = []
    for index in ranked_indices:
        item = dict(items[int(index)])
        item["score"] = round(float(scores[int(index)]), 4)
        selected.append(item)
    return selected


__all__ = ["search_project_memory_items"]
