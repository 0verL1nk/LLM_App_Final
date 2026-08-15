from typing import Any

from .consolidation import MemoryConsolidation, MemoryOperation, process_memory_event
from .repository import (
    ensure_memory_tables,
    list_project_memory_items,
    touch_memory_items,
    upsert_project_memory_item,
)
from .store import ensure_memory_layer_ready, query_long_term_memory

__all__ = [
    "MemoryConsolidation",
    "MemoryOperation",
    "process_memory_event",
    "ensure_memory_tables",
    "upsert_project_memory_item",
    "list_project_memory_items",
    "touch_memory_items",
    "search_project_memory_items",
    "ensure_memory_layer_ready",
    "query_long_term_memory",
]


def __getattr__(name: str) -> Any:
    # Lazy re-export: agent.memory.service pulls the full adapter stack, which
    # loops back into this package through utils.utils during module init.
    if name == "search_project_memory_items":
        from .service import search_project_memory_items

        return search_project_memory_items
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
