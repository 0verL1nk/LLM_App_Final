"""Constrained tool contracts for optional research presentation surfaces."""

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ResearchMapNodeInput(BaseModel):
    """A bounded mind-map node submitted by the model, never rendered directly."""

    label: str = Field(min_length=1, max_length=120)
    children: list["ResearchMapNodeInput"] = Field(default_factory=list, max_length=12)
    citation_ids: list[str] = Field(default_factory=list, max_length=8)


ResearchMapNodeInput.model_rebuild()


class PresentResearchSurfaceInput(BaseModel):
    """Allowed inputs for the single initial PaperSage A2UI surface."""

    title: str = Field(min_length=1, max_length=80)
    root: ResearchMapNodeInput
    presentation: Literal["inline"] = "inline"


@tool(
    "present_research_surface",
    description=(
        "Optionally attach a compact, evidence-grounded research map to the current answer. "
        "Use only when a visual hierarchy substantially improves understanding. "
        "After calling this tool, always continue with a normal Markdown answer and citations."
    ),
    args_schema=PresentResearchSurfaceInput,
)
def present_research_surface(
    title: str,
    root: ResearchMapNodeInput,
    presentation: Literal["inline"] = "inline",
) -> str:
    """Acknowledge a declarative UI request; server code validates and renders it later."""
    return json.dumps(
        {
            "accepted": True,
            "surface": "research_map",
            "presentation": presentation,
            "next": "Continue with a concise Markdown answer grounded in the same evidence.",
        },
        ensure_ascii=False,
    )


def build_a2ui_tools(_deps: object) -> list[object]:
    """Expose only catalog-backed presentation tools to the leader."""
    return [present_research_surface]


__all__ = ["build_a2ui_tools", "present_research_surface"]
