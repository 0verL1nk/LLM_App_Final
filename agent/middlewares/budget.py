"""Runtime-enforced token budget for one agent thread (Codex rollout-budget style).

Unlike prompt-level budgets ("at most N searches"), this middleware counts the
provider-reported token usage of every assistant message already in thread
state and, once the total crosses the limit, strips the model request down to
a no-tools finalize call so the agent delivers what it has instead of looping
until failure.
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

# Deterministic finalize instruction injected once the budget is exhausted.
_BUDGET_EXHAUSTED_INSTRUCTION = (
    "[系统提示] 本任务的 token 预算已耗尽。不要再调用任何工具。"
    "立即基于已收集的信息交付最终结果;未能覆盖的问题列入「未决问题」。"
)


def used_tokens(messages: list[AnyMessage]) -> int:
    """Sum provider-reported total tokens across assistant messages."""
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if isinstance(message, AIMessage) and isinstance(usage, dict):
            value = usage.get("total_tokens")
            if isinstance(value, int) and value > 0:
                total += value
    return total


class TokenBudgetMiddleware(AgentMiddleware[Any, Any, Any]):
    """Cap one thread's total model tokens; finalize instead of failing."""

    def __init__(self, budget_tokens: int) -> None:
        super().__init__()
        if budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")
        self._budget_tokens = budget_tokens

    @property
    def budget_tokens(self) -> int:
        return self._budget_tokens

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Any,
    ) -> ModelResponse[Any]:
        messages = list(request.state.get("messages", [])) if request.state else []
        if used_tokens(messages) < self._budget_tokens:
            return handler(request)
        # Codex-style hard stop: no tools remain on the next call, so the model
        # response ends the agent loop with a delivery instead of another round.
        return handler(
            request.override(
                tools=[],
                tool_choice="none",
                messages=[*messages, HumanMessage(content=_BUDGET_EXHAUSTED_INSTRUCTION)],
            )
        )


__all__ = ["TokenBudgetMiddleware", "used_tokens"]
