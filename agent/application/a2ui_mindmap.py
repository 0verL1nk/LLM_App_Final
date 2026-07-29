"""PaperSage's restricted A2UI v0.9 mind-map catalog and validator."""

from __future__ import annotations

import json
from typing import Any

CATALOG_ID = "https://papersage.local/a2ui/catalogs/mindmap-v1.json"
MAX_CHILDREN = 12
MAX_DEPTH = 5
MAX_LABEL_LENGTH = 120


def parse_a2ui_mindmap_jsonl(text: str) -> dict[str, Any] | None:
    """Validate an ordered A2UI v0.9 JSONL surface without executing input."""
    try:
        messages = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return None
    if len(messages) != 3 or not all(isinstance(item, dict) for item in messages):
        return None
    create = messages[0].get("createSurface")
    components = messages[1].get("updateComponents")
    data = messages[2].get("updateDataModel")
    if not isinstance(create, dict) or not isinstance(components, dict) or not isinstance(data, dict):
        return None
    if any(message.get("version") != "v0.9" for message in messages):
        return None
    surface_id = str(create.get("surfaceId") or "").strip()
    if not surface_id or create.get("catalogId") != CATALOG_ID:
        return None
    if components.get("surfaceId") != surface_id or data.get("surfaceId") != surface_id:
        return None
    definitions = components.get("components")
    if not isinstance(definitions, list) or len(definitions) != 1:
        return None
    root = definitions[0] if isinstance(definitions[0], dict) else {}
    if root.get("id") != "root" or root.get("component") != "Mindmap" or root.get("data") != {"path": "/mindmap"}:
        return None
    value = data.get("value")
    if data.get("path") != "/mindmap" or not isinstance(value, dict):
        return None
    mindmap = _normalize_node(value, depth=0)
    if mindmap is None:
        return None
    return {"catalogId": CATALOG_ID, "surfaceId": surface_id, "messages": messages, "mindmap": mindmap}


def _normalize_node(value: dict[str, Any], *, depth: int) -> dict[str, Any] | None:
    label = str(value.get("label") or "").strip()
    children = value.get("children", [])
    if not label or len(label) > MAX_LABEL_LENGTH or not isinstance(children, list) or len(children) > MAX_CHILDREN:
        return None
    if depth >= MAX_DEPTH and children:
        return None
    normalized_children: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            return None
        normalized = _normalize_node(child, depth=depth + 1)
        if normalized is None:
            return None
        normalized_children.append(normalized)
    return {"label": label, "children": normalized_children}


__all__ = ["CATALOG_ID", "parse_a2ui_mindmap_jsonl"]
