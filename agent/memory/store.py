from typing import Any

from .repository import (
    ensure_memory_tables,
    list_project_memory_items,
    touch_memory_items,
    upsert_project_memory_item,
)

__all__ = [
    "ensure_memory_tables",
    "upsert_project_memory_item",
    "list_project_memory_items",
    "touch_memory_items",
    "search_project_memory_items",
]


def __getattr__(name: str) -> Any:
    # Lazy re-export: agent.memory.service pulls the full adapter stack, which
    # loops back here through utils.utils when both initialize at import time.
    if name == "search_project_memory_items":
        from .service import search_project_memory_items

        return search_project_memory_items
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def ensure_memory_layer_ready(db_name: str = "./database.sqlite") -> None:
    ensure_memory_tables(db_name=db_name)


def query_long_term_memory(
    *,
    uuid: str,
    project_uid: str,
    query: str,
    limit: int = 5,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    return search_project_memory_items(
        uuid=uuid,
        project_uid=project_uid,
        query=query,
        limit=limit,
        db_name=db_name,
    )
