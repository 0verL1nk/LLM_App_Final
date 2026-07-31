from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent.middlewares.todolist import EnhancedTodoListMiddleware
from agent.middlewares.turn_context import TurnContextMiddleware


class _CaptureChatModel(BaseChatModel):
    seen_requests: list[list[Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "capture"

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> "_CaptureChatModel":
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen_requests.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="ok"))]
        )


def test_agent_pipeline_sends_exactly_one_leading_system_message() -> None:
    model = _CaptureChatModel()
    agent = create_agent(
        model=model,
        tools=[],
        system_prompt="Leader base prompt.",
        middleware=[TurnContextMiddleware(), EnhancedTodoListMiddleware()],
    )

    result = agent.invoke(
        {"messages": [HumanMessage(content="你好")]},
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

    assert result["messages"][-1].content == "ok"
    assert len(model.seen_requests) == 1
    provider_messages = model.seen_requests[0]
    assert isinstance(provider_messages[0], SystemMessage)
    assert isinstance(provider_messages[0].content, str)
    assert sum(isinstance(message, SystemMessage) for message in provider_messages) == 1
    assert isinstance(provider_messages[1], HumanMessage)
    system_content = str(provider_messages[0].content)
    assert "Leader base prompt." in system_content
    assert "请使用中文回答" in system_content
    assert "偏好简洁回答" in system_content
    assert "write_todos" in system_content
