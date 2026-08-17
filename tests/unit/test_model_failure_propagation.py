"""Mid-stream model failures must propagate instead of becoming answer text.

Regression guard for the 2026-08-17 incident: an invalid ``on_failure`` value
made ``ModelRetryMiddleware`` format the exception into an ``AIMessage``, which
the messages stream then rendered as answer text (run completed with the
provider error glued into the reply).
"""

from typing import Any, Iterator

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.tools import tool

from agent.middlewares.builder import build_middleware_list


class _MidStreamBoomModel(BaseChatModel):
    """Streams a tool call first, then raises mid-stream on the next turn."""

    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "mid-stream-boom"

    def bind_tools(self, tools: Any, **kwargs: Any) -> BaseChatModel:
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGenerationChunk(message=AIMessage(content="partial"))])

    def _stream(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        object.__setattr__(self, "calls", self.calls + 1)
        if self.calls >= 2:
            yield ChatGenerationChunk(message=AIMessageChunk(content="正在整理后续内容。"))
            raise ValueError("boom mid-stream 400")
        yield ChatGenerationChunk(message=AIMessageChunk(content="先检查一下"))
        yield ChatGenerationChunk(
            message=AIMessageChunk(content="", tool_calls=[{"name": "probe", "args": {}, "id": "c1", "type": "tool_call"}])
        )


@tool
def probe() -> str:
    """Probe."""
    return "ok"


def _collect_deltas(agent: Any) -> Iterator[str]:
    for part in agent.stream(
        {"messages": [{"role": "user", "content": "hi"}]},
        config={"configurable": {"thread_id": "t"}},
        stream_mode=["messages", "values"],
        version="v2",
    ):
        if not isinstance(part, dict) or part.get("type") != "messages":
            continue
        data = part.get("data")
        chunk = data[0] if isinstance(data, tuple) and data else None
        text = getattr(chunk, "content", "") if chunk is not None else ""
        if isinstance(text, str) and text:
            yield text


def test_mid_stream_failure_propagates_instead_of_leaking_into_answer() -> None:
    middleware = build_middleware_list(
        model=_MidStreamBoomModel(),
        profile=None,
        deps=None,
        enable_tool_selector=False,
    )
    agent = create_agent(model=_MidStreamBoomModel(), tools=[probe], system_prompt="t", middleware=middleware)
    deltas: list[str] = []
    with pytest.raises(ValueError, match="boom mid-stream"):
        deltas.extend(_collect_deltas(agent))
    assert not any("Model call failed" in delta for delta in deltas)
