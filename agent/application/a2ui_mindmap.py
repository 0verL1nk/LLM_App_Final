"""PaperSage's restricted A2UI v0.9 mind-map catalog and validator."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

CATALOG_ID = "https://papersage.local/a2ui/catalogs/mindmap-v1.json"
MAX_CHILDREN = 12
MAX_DEPTH = 5
MAX_LABEL_LENGTH = 120
MAX_NODES = 120


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


def build_mindmap_surface_from_request(
    payload: dict[str, Any],
    *,
    allowed_citation_ids: set[str],
) -> dict[str, Any] | None:
    """Compile a validated research-map DTO into the restricted catalog."""
    title = str(payload.get("title") or "").strip()
    root = payload.get("root")
    if not title or len(title) > 80 or not isinstance(root, dict):
        return None
    mindmap = _normalize_node(
        root,
        depth=0,
        allowed_citation_ids=allowed_citation_ids,
        node_count=[0],
    )
    if mindmap is None:
        return None
    # Evidence is resolved after the model stream has completed. Keep the UI
    # instance stable so a later data-model update enriches the same surface.
    fingerprint = sha256(
        json.dumps(
            {"title": title, "mindmap": _surface_identity_node(mindmap)},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    surface_id = f"research-map-{fingerprint}"
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [{"id": "root", "component": "Mindmap", "data": {"path": "/mindmap"}}],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/mindmap",
                "value": mindmap,
            },
        },
    ]
    return {
        "catalogId": CATALOG_ID,
        "surfaceId": surface_id,
        "title": title,
        "messages": messages,
        "mindmap": mindmap,
    }


def build_mindmap_data_update(surface: dict[str, Any]) -> dict[str, Any] | None:
    """Return the one envelope needed to enrich an already-created surface."""
    surface_id = str(surface.get("surfaceId") or "").strip()
    mindmap = surface.get("mindmap")
    if not surface_id or not isinstance(mindmap, dict):
        return None
    return {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": surface_id,
            "path": "/mindmap",
            "value": mindmap,
        },
    }


def _surface_identity_node(node: dict[str, Any]) -> dict[str, Any]:
    """Remove late-bound evidence references from a stable surface identity."""
    return {
        "label": node["label"],
        "children": [_surface_identity_node(child) for child in node["children"]],
    }


def _normalize_node(
    value: dict[str, Any],
    *,
    depth: int,
    allowed_citation_ids: set[str] | None = None,
    node_count: list[int] | None = None,
) -> dict[str, Any] | None:
    label = str(value.get("label") or "").strip()
    children = value.get("children", [])
    if not label or len(label) > MAX_LABEL_LENGTH or not isinstance(children, list) or len(children) > MAX_CHILDREN:
        return None
    if depth >= MAX_DEPTH and children:
        return None
    if node_count is not None:
        node_count[0] += 1
        if node_count[0] > MAX_NODES:
            return None
    normalized_children: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            return None
        normalized = _normalize_node(
            child,
            depth=depth + 1,
            allowed_citation_ids=allowed_citation_ids,
            node_count=node_count,
        )
        if normalized is None:
            return None
        normalized_children.append(normalized)
    normalized = {"label": label, "children": normalized_children}
    if allowed_citation_ids is not None:
        citations = value.get("citation_ids")
        if isinstance(citations, list):
            verified = [
                citation
                for citation in (str(item).strip() for item in citations)
                if citation and citation in allowed_citation_ids
            ]
            if verified:
                normalized["citation_ids"] = list(dict.fromkeys(verified))
    return normalized


__all__ = [
    "CATALOG_ID",
    "build_mindmap_data_update",
    "build_mindmap_surface_from_request",
    "parse_a2ui_mindmap_jsonl",
]
