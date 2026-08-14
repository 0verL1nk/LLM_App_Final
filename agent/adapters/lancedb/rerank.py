"""FlashRank integration for the canonical project retrieval pipeline."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _ranker(model_name: str) -> Any:
    from flashrank import Ranker

    return Ranker(model_name=model_name)


def rerank_rows(
    *,
    query: str,
    rows: list[dict[str, Any]],
    model_name: str,
    enabled: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    """Rerank RRF rows, or return those rows unchanged with an explicit reason."""
    if not rows:
        return [], None
    if not enabled:
        return rows, "rerank_disabled_by_configuration"
    try:
        from flashrank import RerankRequest

        ranked = _ranker(model_name).rerank(
            RerankRequest(
                query=query,
                passages=[{"id": str(index), "text": str(row.get("text") or "")}
                           for index, row in enumerate(rows)],
            )
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        logger.warning("Project retrieval rerank skipped: %s", exc)
        return rows, f"rerank_skipped:{type(exc).__name__}"

    ordered: list[dict[str, Any]] = []
    for item in ranked:
        try:
            index = int(item["id"] if isinstance(item, dict) else item.id)
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.warning("Project retrieval rerank returned an invalid passage id")
            return rows, "rerank_skipped:invalid_result"
        if 0 <= index < len(rows):
            row = dict(rows[index])
            score = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
            if isinstance(score, (int, float)):
                row["_rerank_score"] = float(score)
            ordered.append(row)
    if len(ordered) != len(rows):
        logger.warning("Project retrieval rerank omitted one or more passages")
        return rows, "rerank_skipped:incomplete_result"
    return ordered, None


__all__ = ["rerank_rows"]
