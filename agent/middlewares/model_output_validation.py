"""Validate provider responses before the Agent accepts them as a completed step."""

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

from ..application.contracts import EmptyModelOutputError


def _has_visible_content(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list):
        return bool(str(content or "").strip())
    for block in content:
        if isinstance(block, str) and block.strip():
            return True
        if isinstance(block, dict):
            text = block.get("text") or block.get("content")
            if isinstance(text, str) and text.strip():
                return True
    return False


class ModelOutputValidationMiddleware(AgentMiddleware):
    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        response = handler(request)
        last_message = next(
            (item for item in reversed(list(response.result or [])) if isinstance(item, AIMessage)),
            None,
        )
        if last_message is None:
            raise EmptyModelOutputError("Model response did not contain an assistant message")
        if not _has_visible_content(last_message.content) and not last_message.tool_calls:
            raise EmptyModelOutputError("Model response contained no text or tool calls")
        return response


model_output_validation_middleware = ModelOutputValidationMiddleware()

__all__ = [
    "EmptyModelOutputError",
    "ModelOutputValidationMiddleware",
    "model_output_validation_middleware",
]
