"""Provider-facing LLM request and response logging middleware."""

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


class LLMLoggerMiddleware(AgentMiddleware):
    """Log the final request that is passed to the model provider."""

    @staticmethod
    def _log_input(request: ModelRequest[Any]) -> None:
        messages = list(request.messages or [])

        try:
            recent_messages = messages[-5:] if len(messages) > 5 else messages
            input_log: list[dict[str, str]] = []
            if request.system_message is not None:
                input_log.append(
                    {
                        "role": "system",
                        "content": str(request.system_message.content)[:1000],
                    }
                )
            for msg in recent_messages:
                role = getattr(msg, "type", "unknown")
                content = getattr(msg, "content", "")
                input_log.append({"role": role, "content": str(content)[:500]})

            logger.info("LLM_INPUT: %s", json.dumps(input_log, ensure_ascii=False))
        except Exception as e:
            logger.warning("Failed to log LLM input: %s", e)

    @staticmethod
    def _log_output(response: ModelResponse[Any]) -> None:
        result = list(response.result or [])
        last_msg = next((item for item in reversed(result) if isinstance(item, AIMessage)), None)
        if last_msg is None:
            return None

        try:
            role = getattr(last_msg, "type", "unknown")
            content = getattr(last_msg, "content", "")
            tool_calls = getattr(last_msg, "tool_calls", None)

            output_log = {
                "role": role,
                "content": str(content)[:1000],
                "has_tool_calls": bool(tool_calls),
            }

            if tool_calls:
                output_log["tool_calls"] = [
                    {"name": tc.get("name"), "args": str(tc.get("args", ""))[:200]}
                    for tc in (tool_calls if isinstance(tool_calls, list) else [])
                ]

            logger.info("LLM_OUTPUT: %s", json.dumps(output_log, ensure_ascii=False))
        except Exception as e:
            logger.warning("Failed to log LLM output: %s", e)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        self._log_input(request)
        response = handler(request)
        self._log_output(response)
        return response


llm_logger_middleware = LLMLoggerMiddleware()
