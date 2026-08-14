"""Runtime mechanics shared by the canonical turn execution use case."""

from __future__ import annotations

from typing import Any

from ..domain.trace import phase_summary
from ..stream import extract_stream_text
from .contracts import EventCallback
from .ports import AgentInvoker


def execute_agent_with_streaming(
    *,
    leader_agent: AgentInvoker,
    input_messages: list[Any],
    config: dict[str, Any],
    on_delta: EventCallback | None,
) -> dict[str, Any]:
    """Run once while forwarding final-answer chunks and retaining final state."""
    stream = getattr(leader_agent, "stream", None)
    if not callable(stream):
        return leader_agent.invoke({"messages": input_messages}, config=config)

    final_state: dict[str, Any] | None = None
    received_stream_part = False
    try:
        for part in stream(
            {"messages": input_messages},
            config=config,
            stream_mode=["messages", "values"],
            version="v2",
        ):
            received_stream_part = True
            if not isinstance(part, dict):
                continue
            if part.get("type") == "messages":
                delta = extract_stream_text(part.get("data"))
                if delta and on_delta is not None:
                    on_delta({"performative": "answer_delta", "content": delta})
            elif part.get("type") == "values" and isinstance(part.get("data"), dict):
                final_state = part["data"]
    except (TypeError, NotImplementedError):
        final_state = None

    if final_state is not None:
        return final_state
    if received_stream_part:
        raise RuntimeError("Agent stream ended without a final state")
    return leader_agent.invoke({"messages": input_messages}, config=config)


def build_phase_path(*, phase_labels: list[str], answer: str, messages: list[Any]) -> str:
    """Ensure a non-empty completed turn always exposes a final-answer phase."""
    normalized_labels = list(phase_labels)
    if (answer.strip() or messages) and (
        not normalized_labels or normalized_labels[-1] != "输出最终答案"
    ):
        normalized_labels.append("输出最终答案")
    return phase_summary(normalized_labels)
