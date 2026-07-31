import logging

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.middlewares.llm_logger import LLMLoggerMiddleware
from agent.middlewares.todolist import EnhancedTodoListMiddleware
from agent.middlewares.turn_context import TurnContextMiddleware


def test_turn_context_and_todo_share_one_provider_system_message(caplog) -> None:
    state = {
        "messages": [HumanMessage(content="你好")],
        "turn_system_context": "请使用中文回答。",
    }
    initial_request = ModelRequest(
        model="llm",  # type: ignore[arg-type]
        messages=list(state["messages"]),
        system_message=SystemMessage(content="Leader base prompt."),
        state=state,
    )
    turn_context = TurnContextMiddleware()
    todo = EnhancedTodoListMiddleware(system_prompt="Todo planning instructions.")
    llm_logger = LLMLoggerMiddleware()
    captured: list[ModelRequest[None]] = []

    def _provider(request: ModelRequest[None]) -> ModelResponse[None]:
        captured.append(request)
        return ModelResponse(result=[AIMessage(content="你好，有什么可以帮你？")])

    def _with_logger(request: ModelRequest[None]) -> ModelResponse[None]:
        return llm_logger.wrap_model_call(request, _provider)

    def _with_todo(request: ModelRequest[None]) -> ModelResponse[None]:
        return todo.wrap_model_call(request, _with_logger)

    with caplog.at_level(logging.INFO, logger="agent.middlewares.llm_logger"):
        response = turn_context.wrap_model_call(initial_request, _with_todo)

    assert response.result[0].content == "你好，有什么可以帮你？"
    assert len(captured) == 1
    provider_request = captured[0]
    assert provider_request.system_message is not None
    assert isinstance(provider_request.system_message.content, str)
    system_content = str(provider_request.system_message.content)
    assert "Leader base prompt." in system_content
    assert "请使用中文回答。" in system_content
    assert "Todo planning instructions." in system_content
    assert not any(
        isinstance(message, SystemMessage) for message in provider_request.messages
    )
    assert "Leader base prompt." in caplog.text
    assert '"role": "human", "content": "你好"' in caplog.text
    assert "你好，有什么可以帮你？" in caplog.text
