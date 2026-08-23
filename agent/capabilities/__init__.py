from collections.abc import Callable, Iterable
from typing import Any

from .document import build_document_tools
from .human import build_human_tools
from .paper import build_paper_tools
from .planning import build_planning_tools
from .skill import build_skill_tools
from .web import build_web_tools


def build_capability_tools(capability_ids: Iterable[str], deps: Any) -> list[Any]:
    """Build a deduplicated tool set for an explicit capability manifest."""
    builders: dict[str, Callable[[Any], list[Any]]] = {
        "document_pack": build_document_tools,
        "human_pack": build_human_tools,
        "paper_pack": build_paper_tools,
        "planning_pack": build_planning_tools,
        "skill_pack": build_skill_tools,
        "web_pack": build_web_tools,
    }
    tools: list[Any] = []
    seen_names: set[str] = set()
    for capability_id in capability_ids:
        if capability_id == "document_pack" and getattr(deps, "document_access", "scoped") == "none":
            continue
        builder = builders.get(str(capability_id))
        if builder is None:
            raise ValueError(f"Unknown capability id: {capability_id}")
        for tool_item in builder(deps):
            name = str(getattr(tool_item, "name", "") or "").strip()
            key = name or repr(tool_item)
            if key in seen_names:
                continue
            seen_names.add(key)
            tools.append(tool_item)
    return tools


def build_profile_tools(profile: Any, deps: Any) -> list[Any]:
    return build_capability_tools(getattr(profile, "capability_ids", ()), deps)


__all__ = ["build_capability_tools", "build_profile_tools"]
