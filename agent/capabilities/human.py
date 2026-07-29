"""Leader-only human confirmation capability."""

import json
from typing import Literal

from langchain_core.tools import tool


@tool
def ask_human(
    question: str,
    context: str = "",
    urgency: Literal["low", "normal", "high"] = "normal",
) -> str:
    """Request a human decision only when ambiguity or approval blocks safe progress."""
    return json.dumps(
        {
            "type": "ask_human",
            "question": str(question or "").strip(),
            "context": str(context or "").strip(),
            "urgency": urgency,
        },
        ensure_ascii=False,
    )


def build_human_tools(_deps: object) -> list[object]:
    return [ask_human]


__all__ = ["ask_human", "build_human_tools"]
