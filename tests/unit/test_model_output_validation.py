from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from agent.middlewares.model_output_validation import (
    EmptyModelOutputError,
    ModelOutputValidationMiddleware,
)


def test_model_output_validation_rejects_empty_terminal_message() -> None:
    middleware = ModelOutputValidationMiddleware()
    response = Mock(result=[AIMessage(content="")])

    with pytest.raises(EmptyModelOutputError, match="no text or tool calls"):
        middleware.wrap_model_call(Mock(), lambda _request: response)


def test_model_output_validation_accepts_tool_call_without_text() -> None:
    middleware = ModelOutputValidationMiddleware()
    message = AIMessage(
        content="",
        tool_calls=[{"name": "search_document", "args": {"query": "GPT"}, "id": "call-1"}],
    )
    response = Mock(result=[message])

    assert middleware.wrap_model_call(Mock(), lambda _request: response) is response
