"""Provider-boundary hygiene for replayed conversation history.

Legacy threads (before the 2026-08-17 on_failure fix) carry assistant
messages whose content is a provider error string, and follow-up delivery
can leave consecutive human messages. Strict OpenAI-compatible providers
reject both with opaque 400 "invalid params" errors that then repeat on
every turn because the poisoned history replays forever. This middleware
cleans what is SENT to the provider on each call; stored state is not
rewritten.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

# The 2026-08-17 retry-middleware incident formatted exceptions into
# AIMessages with this exact prefix; they carry no model output.
_FAILURE_ARTIFACT_PREFIX = "Model call failed after"


def sanitize_messages_for_provider(messages: list[Any]) -> list[Any]:
    """Drop failure artifacts and merge consecutive same-role human turns."""
    cleaned: list[Any] = []
    for message in messages:
        if getattr(message, "type", "") == "ai" and str(
            getattr(message, "content", "") or ""
        ).startswith(_FAILURE_ARTIFACT_PREFIX):
            continue
        cleaned.append(message)
    merged: list[Any] = []
    for message in cleaned:
        previous = merged[-1] if merged else None
        if (
            getattr(message, "type", "") == "human"
            and getattr(previous, "type", "") == "human"
        ):
            merged[-1] = message.__class__(
                content=f"{previous.content}\n\n{message.content}",
                **(
                    {"name": previous.name}
                    if getattr(previous, "name", None)
                    else {}
                ),
            )
            continue
        merged.append(message)
    return merged


class ProviderHistoryHygieneMiddleware(AgentMiddleware):
    """Strip error artifacts and role runs from each outgoing model request."""

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        sanitized = sanitize_messages_for_provider(list(request.messages))
        if len(sanitized) != len(request.messages):
            request.messages[:] = sanitized
        return handler(request)


provider_history_hygiene_middleware = ProviderHistoryHygieneMiddleware()
