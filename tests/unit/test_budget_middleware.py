"""TokenBudgetMiddleware behavior (Codex rollout-budget analogue)."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from agent.middlewares.budget import TokenBudgetMiddleware, used_tokens


def test_used_tokens_sums_provider_reported_totals() -> None:
    messages = [
        AIMessage(content="a", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
        HumanMessage(content="b"),
        AIMessage(content="c", usage_metadata={"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}),
        AIMessage(content="no usage"),
    ]
    assert used_tokens(messages) == 40


def _fake_request(state_messages: list[Any], tools: list[Any]) -> Any:
    from langchain.agents.middleware.types import ModelRequest

    return ModelRequest(
        model=_DummyModel(),
        messages=list(state_messages),
        tools=list(tools),
        state={"messages": list(state_messages)},
    )


class _DummyModel:
    pass


@tool
def _probe() -> str:
    """Probe tool."""
    return "ok"


def _recording_handler(seen: list[Any]):
    def handler(request: Any) -> str:
        seen.append(request)
        return "response"

    return handler


def test_budget_passes_through_below_limit() -> None:
    seen: list[Any] = []
    request = _fake_request(
        [AIMessage(content="m", usage_metadata={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10})],
        [_probe],
    )
    result = TokenBudgetMiddleware(budget_tokens=100).wrap_model_call(request, _recording_handler(seen))
    assert result == "response"
    assert seen[0] is request  # unchanged request below the budget


def test_budget_finalizes_without_tools_at_limit() -> None:
    seen: list[Any] = []
    heavy = AIMessage(
        content="m",
        usage_metadata={"input_tokens": 500, "output_tokens": 500, "total_tokens": 1000},
    )
    request = _fake_request([heavy], [_probe])
    TokenBudgetMiddleware(budget_tokens=500).wrap_model_call(request, _recording_handler(seen))
    finalized = seen[0]
    assert finalized.tools == []
    assert finalized.tool_choice == "none"
    injected = finalized.messages[-1]
    assert "token 预算已耗尽" in injected.content
    assert any("未决问题" in part for part in [injected.content])


def test_budget_rejects_non_positive_limit() -> None:
    import pytest

    with pytest.raises(ValueError):
        TokenBudgetMiddleware(budget_tokens=0)
