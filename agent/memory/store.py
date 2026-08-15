from typing import TYPE_CHECKING, Any

from .repository import (
    ensure_memory_tables,
    list_project_memory_items,
    touch_memory_items,
    upsert_project_memory_item,
)

if TYPE_CHECKING:
    # Import-only for static analysis; the runtime import stays lazy to
    # break the service -> adapters -> utils -> store import cycle.
    from .service import search_project_memory_items

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
    # Module __getattr__ never satisfies bare-name lookups inside functions,
    # so resolve the facade member lazily here.
    from .service import search_project_memory_items

    return search_project_memory_items(
        uuid=uuid,
        project_uid=project_uid,
        query=query,
        limit=limit,
        db_name=db_name,
    )
