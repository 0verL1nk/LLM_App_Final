from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.middlewares.turn_context import TurnContextMiddleware


def _request(state: dict) -> ModelRequest[None]:
    return ModelRequest(
        model="llm",  # type: ignore[arg-type]
        messages=list(state["messages"]),
        system_message=SystemMessage(content="Base leader instructions."),
        state=state,
    )


def test_turn_context_middleware_merges_context_into_provider_system_message() -> None:
    middleware = TurnContextMiddleware()
    state = {"messages": [HumanMessage(content="真实用户问题")]}

    update = middleware.before_model(
        state,
        runtime=None,
        config={
            "configurable": {
                "turn_context": {
                    "response_language": "zh",
                    "memory_items": [
                        {"memory_type": "semantic", "content": "偏好简洁回答"}
                    ],
                }
            }
        },
    )
    assert isinstance(update, dict)
    state.update(update)

    captured: list[ModelRequest[None]] = []

    def _handler(request: ModelRequest[None]) -> ModelResponse[None]:
        captured.append(request)
        return ModelResponse(result=[AIMessage(content="完成")])

    middleware.wrap_model_call(_request(state), _handler)

    assert len(captured) == 1
    request = captured[0]
    assert request.system_message is not None
    content = str(request.system_message.content)
    assert "Base leader instructions." in content
    assert "请使用中文回答" in content
    assert "Semantically retrieved long-term memory candidates" in content
    assert "only when it is directly relevant" in content
    assert request.messages == state["messages"]
    assert not any(isinstance(message, SystemMessage) for message in request.messages)


def test_turn_context_middleware_clears_empty_context() -> None:
    middleware = TurnContextMiddleware()
    state = {"messages": [HumanMessage(content="hello")]}

    update = middleware.before_model(
        state,
        runtime=None,
        config={"configurable": {"turn_context": {}}},
    )

    assert update == {"turn_system_context": ""}
