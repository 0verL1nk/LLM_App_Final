from agent.middlewares.todolist import Todo, write_todos


def test_todo_model_contains_only_planning_fields() -> None:
    todo = Todo(
        id="todo-1",
        content="检索证据",
        status="ready",
        depends_on=[],
    )

    payload = todo.model_dump()

    assert payload == {
        "id": "todo-1",
        "content": "检索证据",
        "status": "ready",
        "depends_on": [],
    }


def test_write_todos_preserves_planning_fields_in_state_update() -> None:
    todo = Todo(
        id="todo-1",
        content="检索证据",
        status="ready",
        depends_on=[],
    )

    command = write_todos.func([todo], "tool-call-1")
    update = command.update or {}
    updated_todos = update["todos"]

    assert updated_todos[0].id == "todo-1"
    assert updated_todos[0].status == "ready"


def test_write_todos_injects_scheduler_hint_for_leader_decision() -> None:
    todos = [
        Todo(id="todo-1", content="检索证据", status="completed", depends_on=[]),
        Todo(id="todo-2", content="整理证据", status="pending", depends_on=["todo-1"]),
        Todo(id="todo-3", content="撰写总结", status="pending", depends_on=["todo-x"]),
    ]

    command = write_todos.func(todos, "tool-call-2")
    update = command.update or {}
    hint = update["todo_scheduler_hint"]

    assert hint["ready_todo_ids"] == ["todo-2"]
    assert hint["blocked_todo_ids"] == []
    assert hint["completed_todo_ids"] == ["todo-1"]
