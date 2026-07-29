from agent.application.run_timeline import project_runtime_event


def test_projects_actual_tool_lifecycle_with_safe_payload() -> None:
    event_type, payload = project_runtime_event(
        {
            "performative": "tool_call",
            "metadata": {
                "tool_name": "search_document",
                "tool_call_id": "call-1",
                "arguments": {"query": "RAG", "api_key": "secret"},
            },
        }
    )

    assert event_type == "tool.execution.started"
    assert payload["toolName"] == "search_document"
    assert payload["arguments"] == {"query": "RAG", "api_key": "[redacted]"}


def test_projects_real_todo_and_delegation_events() -> None:
    plan_type, plan_payload = project_runtime_event(
        {
            "performative": "tool_call",
            "metadata": {
                "tool_name": "write_todos",
                "tool_call_id": "call-plan",
                "arguments": {"todos": [{"id": "read", "content": "Read paper", "status": "pending"}]},
            },
        }
    )
    delegate_type, delegate_payload = project_runtime_event(
        {
            "performative": "tool_result",
            "metadata": {
                "tool_name": "task",
                "tool_call_id": "call-agent",
                "arguments": {"subagent_type": "researcher", "description": "Compare methods"},
                "status": "success",
                "duration_ms": 42,
            },
        }
    )

    assert plan_type == "plan.updated"
    assert plan_payload["todos"][0]["id"] == "read"
    assert delegate_type == "agent.completed"
    assert delegate_payload["agent"] == "researcher"
    assert delegate_payload["task"] == "Compare methods"
    assert delegate_payload["durationMs"] == 42.0


def test_projects_answer_delta_as_a_distinct_stream_event() -> None:
    event_type, payload = project_runtime_event({"performative": "answer_delta", "content": "逐字输出"})

    assert event_type == "answer.delta"
    assert payload == {"text": "逐字输出"}
