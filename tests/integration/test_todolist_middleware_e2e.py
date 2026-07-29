"""Integration test for TodoListMiddleware registration."""

from langchain_core.language_models import FakeListChatModel

from agent.middlewares.todolist import todolist_middleware
from agent.runtime_agent import create_runtime_agent


def test_todolist_middleware_provides_write_todos_tool() -> None:
    """Test that TodoListMiddleware provides write_todos tool to the agent."""
    model = FakeListChatModel(responses=["好的，我会帮你规划项目。"])

    agent = create_runtime_agent(
        model=model,
        system_prompt="你是一个助手。",
        tools=[],
        middleware=[todolist_middleware],
    )

    assert agent is not None
    assert [tool.name for tool in todolist_middleware.tools] == ["write_todos"]
