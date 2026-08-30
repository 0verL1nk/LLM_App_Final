"""Middleware builder for agent runtime."""

from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
)
from openai import RateLimitError

from ..context_governance import compact_trigger_ratio, model_context_window_tokens
from ..subagent.loader import load_subagent_definitions
from .budget import TokenBudgetMiddleware
from .durable_delegation import DurableDelegationMiddleware
from .llm_logger import llm_logger_middleware
from .model_output_validation import (
    EmptyModelOutputError,
    model_output_validation_middleware,
)
from .plan import plan_middleware
from .provider_history_hygiene import provider_history_hygiene_middleware
from .steering_input import steering_input_middleware
from .tool_selector import build_tool_selector_middleware
from .trace import TraceMiddleware
from .turn_context import turn_context_middleware

_RUNTIME_MIDDLEWARE_IDS = (
    "trace",
    "llm_logger",
    "plan",
)


def _is_enabled(profile: Any | None, middleware_id: str) -> bool:
    if profile is None:
        return middleware_id in _RUNTIME_MIDDLEWARE_IDS
    return middleware_id in set(getattr(profile, "middleware_ids", ()))


def build_middleware_list(
    model: Any,
    profile: Any | None = None,
    deps: Any | None = None,
    enable_auto_summarization: bool = True,
    enable_tool_selector: bool = True,
    max_turn_tokens: int | None = None,
) -> list[AgentMiddleware[Any, Any, Any]]:
    """Build complete middleware list for agent runtime."""
    middleware_list: list[AgentMiddleware[Any, Any, Any]] = []

    if max_turn_tokens is not None:
        middleware_list.append(TokenBudgetMiddleware(max_turn_tokens))

    if _is_enabled(profile, "trace"):
        middleware_list.append(TraceMiddleware())

    middleware_list.append(
        ModelRetryMiddleware(
            max_retries=5,
            retry_on=(RateLimitError, EmptyModelOutputError),
            backoff_factor=2.0,
            initial_delay=1.0,
            max_delay=60.0,
            jitter=True,
            # Valid values are "error" (re-raise) or a callable; anything else
            # silently converts the exception into an AIMessage, which the
            # stream then renders as answer text (seen live on 2026-08-17).
            on_failure="error",
        )
    )

    middleware_list.append(turn_context_middleware)
    middleware_list.append(steering_input_middleware)
    # Legacy threads replay provider-error artifacts and consecutive human
    # turns; strict providers (e.g. MiniMax) answer those with 400 forever.
    middleware_list.append(provider_history_hygiene_middleware)

    if _is_enabled(profile, "subagent"):
        if deps is None:
            raise ValueError("Subagent middleware requires runtime dependencies")
        definitions = load_subagent_definitions()
        if definitions:
            middleware_list.append(DurableDelegationMiddleware(definitions))

    if _is_enabled(profile, "plan"):
        middleware_list.append(plan_middleware)

    if enable_tool_selector:
        middleware_list.append(build_tool_selector_middleware(model))

    if enable_auto_summarization:
        middleware_list.append(
            SummarizationMiddleware(
                model=model,
                trigger=(
                    "tokens",
                    int(model_context_window_tokens() * compact_trigger_ratio()),
                ),
                keep=("messages", 20),
            )
        )

    middleware_list.append(model_output_validation_middleware)

    # Keep logging innermost so it observes the final provider-facing request
    # after system instructions, tools, and summaries have been resolved.
    if _is_enabled(profile, "llm_logger"):
        middleware_list.append(llm_logger_middleware)

    return middleware_list


__all__ = ["build_middleware_list"]
