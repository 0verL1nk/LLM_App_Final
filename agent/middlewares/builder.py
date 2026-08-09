"""Middleware builder for agent runtime."""

from typing import Any

from deepagents import CompiledSubAgent, SubAgent
from deepagents.backends import StateBackend
from deepagents.middleware.subagents import SubAgentMiddleware
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
)
from openai import RateLimitError

from ..capabilities import build_capability_tools
from ..context_governance import compact_trigger_ratio, model_context_window_tokens
from ..subagent.loader import load_subagent_definitions
from .llm_logger import llm_logger_middleware
from .model_output_validation import (
    EmptyModelOutputError,
    model_output_validation_middleware,
)
from .plan import plan_middleware
from .subagent_lifecycle import SubagentLifecycleMiddleware
from .todolist import todolist_middleware
from .tool_selector import build_tool_selector_middleware
from .trace import TraceMiddleware
from .turn_context import turn_context_middleware

_RUNTIME_MIDDLEWARE_IDS = (
    "trace",
    "llm_logger",
    "todolist",
    "plan",
)


def _build_runtime_subagent_specs(
    model: Any,
    deps: Any,
) -> list[SubAgent | CompiledSubAgent]:
    """Build bounded subagents with only their declared capabilities."""
    subagent_specs: list[SubAgent | CompiledSubAgent] = []

    for definition in load_subagent_definitions():
        spec: SubAgent = {
            "name": definition.name,
            "description": definition.description,
            "system_prompt": definition.system_prompt,
            "model": definition.model or model,
            "tools": build_capability_tools(definition.capability_ids, deps),
            "middleware": [SubagentLifecycleMiddleware(definition.name)],
        }
        subagent_specs.append(spec)

    return subagent_specs


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
) -> list[AgentMiddleware[Any, Any, Any]]:
    """Build complete middleware list for agent runtime."""
    middleware_list: list[AgentMiddleware[Any, Any, Any]] = []

    if _is_enabled(profile, "trace"):
        middleware_list.append(TraceMiddleware())

    middleware_list.append(
        ModelRetryMiddleware(
            max_retries=3,
            retry_on=(RateLimitError, EmptyModelOutputError),
            backoff_factor=2.0,
            initial_delay=1.0,
            max_delay=60.0,
            jitter=True,
            on_failure="raise",
        )
    )

    middleware_list.append(turn_context_middleware)

    if _is_enabled(profile, "subagent"):
        if deps is None:
            raise ValueError("Subagent middleware requires runtime dependencies")
        subagent_specs = _build_runtime_subagent_specs(model, deps)
        if subagent_specs:
            middleware_list.append(
                SubAgentMiddleware(
                    backend=StateBackend,
                    subagents=subagent_specs,
                )
            )

    if _is_enabled(profile, "todolist"):
        middleware_list.append(todolist_middleware)

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
