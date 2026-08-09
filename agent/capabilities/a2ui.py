"""Presentation capability boundary for the leader agent."""

from typing import Any

from ..tools.a2ui import build_a2ui_tools


def build_a2ui_capability_tools(deps: Any) -> list[Any]:
    """Build catalog-backed A2UI tools without exposing renderer internals."""
    return build_a2ui_tools(deps)


__all__ = ["build_a2ui_capability_tools"]
