"""Enhanced TodoList middleware with dependency management.

Based on LangChain's official TodoListMiddleware, with added support for
task dependencies, cycle detection, and topological sorting.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    OmitFromInput,
)
from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..domain.todo_graph import TodoGraph
from .system_message import append_system_instruction


class Todo(BaseModel):
    """A single todo item with content, status, and optional dependencies."""

    id: str = Field(description="Unique identifier for the todo item")
    content: str = Field(description="The content/description of the todo item")
    status: Literal[
        "pending",
        "ready",
        "in_progress",
        "completed",
        "blocked",
        "failed",
        "canceled",
    ] = Field(description="The current status of the todo item")
    depends_on: list[str] | None = Field(default=None, description="Optional list of todo IDs that this todo depends on")


class PlanningState(AgentState):
    """State schema for the enhanced todo middleware."""

    todos: Annotated[list[Todo] | None, OmitFromInput]
    """List of todo items with dependency tracking."""


WRITE_TODOS_TOOL_DESCRIPTION = """Use this tool to create and manage a structured task list with dependency tracking.

## When to Use
- Complex multi-step tasks (3+ steps)
- Tasks with dependencies between steps
- User explicitly requests todo list
- User provides multiple tasks

## When NOT to Use
- Single straightforward task
- Trivial tasks (<3 steps)
- Purely conversational requests

## Task Dependencies
- Use `depends_on` field to specify task dependencies
- System will detect circular dependencies
- Only tasks with satisfied dependencies are executable

## Task States
- pending: Not yet started
- in_progress: Currently working on
- completed: Finished successfully

## Best Practices
- Mark tasks in_progress BEFORE starting
- Mark completed IMMEDIATELY after finishing
- Update dependencies as you discover new requirements
- Remove irrelevant tasks from the list"""


WRITE_TODOS_SYSTEM_PROMPT = """## `write_todos`

You have access to the `write_todos` tool with dependency management.
Use this for complex objectives to track progress and manage task dependencies.

Key features:
- Specify task dependencies using `depends_on` field
- System detects circular dependencies automatically
- View executable tasks (dependencies satisfied)
- Use returned scheduler hints to decide which todo to execute next

Mark todos as completed immediately after finishing each step."""


@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
def write_todos(
    todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command[Any]:
    """Create and manage a structured task list with dependencies."""
    # Convert Pydantic models to dicts for TodoGraph
    todos_dict = [t.model_dump() for t in todos]

    # Validate no circular dependencies
    graph = TodoGraph(todos_dict)
    if graph.has_cycle():
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: Circular dependency detected in todo list. "
                        "Please check the depends_on fields.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    # Get executable todos for user feedback
    executable = graph.get_ready_todos()
    executable_ids = [t["id"] for t in executable]
    blocked_ids = [t["id"] for t in graph.get_blocked_todos()]
    completed_ids = [
        str(todo.get("id") or "").strip()
        for todo in todos_dict
        if str(todo.get("status") or "").strip().lower() == "completed"
    ]
    in_progress_ids = [
        str(todo.get("id") or "").strip()
        for todo in todos_dict
        if str(todo.get("status") or "").strip().lower() == "in_progress"
    ]

    return Command(
        update={
            "todos": todos,
            "todo_scheduler_hint": {
                "ready_todo_ids": executable_ids,
                "blocked_todo_ids": blocked_ids,
                "completed_todo_ids": completed_ids,
                "in_progress_todo_ids": in_progress_ids,
            },
            "messages": [
                ToolMessage(
                    (
                        "Updated todo list. "
                        f"Ready: {executable_ids}; Blocked: {blocked_ids}; "
                        f"Completed: {completed_ids}."
                    ),
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


class EnhancedTodoListMiddleware(AgentMiddleware):
    """Enhanced TodoList middleware with dependency management."""

    state_schema = PlanningState

    def __init__(
        self,
        *,
        system_prompt: str = WRITE_TODOS_SYSTEM_PROMPT,
        tool_description: str = WRITE_TODOS_TOOL_DESCRIPTION,
    ) -> None:
        """Initialize the middleware with optional custom prompts."""
        super().__init__()
        self.system_prompt = system_prompt
        self.tool_description = tool_description
        self.tools = [write_todos]

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        """Merge planning instructions into the single provider system message."""
        system_message = append_system_instruction(request.system_message, self.system_prompt)
        return handler(request.override(system_message=system_message))


# Create default instance for backward compatibility
todolist_middleware = EnhancedTodoListMiddleware()

__all__ = ["EnhancedTodoListMiddleware", "todolist_middleware", "Todo", "PlanningState"]
