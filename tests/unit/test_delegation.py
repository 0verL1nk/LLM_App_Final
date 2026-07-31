from langchain_core.messages import AIMessage, ToolMessage

from agent.application.delegation import build_delegation_execution


def test_build_delegation_execution_tracks_sequential_rounds_and_failure() -> None:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "first",
                    "name": "task",
                    "args": {"subagent_type": "researcher", "description": "research"},
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="evidence <evidence>doc-1:chunk_2|p3|o10-20</evidence>",
            tool_call_id="first",
            name="task",
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "second",
                    "name": "task",
                    "args": {"subagent_type": "reviewer", "description": "review"},
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="invalid evidence",
            tool_call_id="second",
            name="task",
            status="error",
        ),
    ]

    execution = build_delegation_execution(messages)

    assert execution["rounds"] == 2
    assert [task["round"] for task in execution["tasks"]] == [1, 2]
    assert [task["status"] for task in execution["tasks"]] == ["completed", "failed"]
    assert not any(task["parallel"] for task in execution["tasks"])
    assert execution["tasks"][0]["evidence_refs"] == ["doc-1:chunk_2|p3|o10-20"]


def test_build_delegation_execution_ignores_non_task_tools() -> None:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "search",
                    "name": "search_document",
                    "args": {"query": "RAG"},
                    "type": "tool_call",
                }
            ],
        )
    ]

    assert build_delegation_execution(messages) == {
        "enabled": False,
        "rounds": 0,
        "member_count": 0,
        "roles": [],
        "tasks": [],
    }


def test_build_delegation_execution_uses_observed_overlap() -> None:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "a",
                    "name": "task",
                    "args": {"subagent_type": "researcher", "description": "find"},
                    "type": "tool_call",
                },
                {
                    "id": "b",
                    "name": "task",
                    "args": {"subagent_type": "reviewer", "description": "check"},
                    "type": "tool_call",
                },
            ],
        ),
        ToolMessage(content="done", tool_call_id="a", name="task"),
        ToolMessage(content="done", tool_call_id="b", name="task"),
    ]
    events = [
        {
            "performative": "subagent_complete",
            "content": '{"role":"researcher","description":"find",'
            '"started_at_ms":100,"completed_at_ms":300,"duration_ms":200}',
        },
        {
            "performative": "subagent_complete",
            "content": '{"role":"reviewer","description":"check",'
            '"started_at_ms":200,"completed_at_ms":400,"duration_ms":200}',
        },
    ]

    execution = build_delegation_execution(messages, events)

    assert all(task["parallel_requested"] for task in execution["tasks"])
    assert all(task["parallel"] for task in execution["tasks"])
    assert execution["tasks"][0]["duration_ms"] == 200.0
