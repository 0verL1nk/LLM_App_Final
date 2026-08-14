from agent.application.run_timeline import project_runtime_item_event


def test_projects_tool_lifecycle_as_a_versioned_item() -> None:
    started = project_runtime_item_event(
        {"performative": "tool_call", "metadata": {"tool_name": "search_document", "tool_call_id": "call-1"}}
    )
    completed = project_runtime_item_event(
        {"performative": "tool_result", "metadata": {"tool_name": "search_document", "tool_call_id": "call-1", "status": "success", "summary": "找到 3 条资料"}}
    )

    assert started == {
        "item_uid": "item_tool_call_call-1",
        "item_type": "tool_call",
        "task_uid": None,
        "status": "in_progress",
        "event_type": "item.created",
        "payload": {"summary": "", "toolName": "search_document", "durationMs": None},
    }
    assert completed is not None
    assert completed["item_uid"] == started["item_uid"]
    assert completed["event_type"] == "item.completed"
    assert completed["payload"]["summary"] == "找到 3 条资料"


def test_projects_text_and_reasoning_parts_as_distinct_item_deltas() -> None:
    text = project_runtime_item_event(
        {"performative": "answer_part_delta", "content": "逐字输出", "metadata": {"part_id": "text-0"}}
    )
    reasoning = project_runtime_item_event(
        {"performative": "answer_part_delta", "content": "展示安全的摘要", "metadata": {"part_id": "reasoning-0"}}
    )

    assert text == {
        "item_uid": "item_assistant_message_text-0",
        "item_type": "assistant_message",
        "task_uid": None,
        "status": "in_progress",
        "event_type": "item.delta",
        "payload": {"partId": "text-0", "delta": "逐字输出"},
    }
    assert reasoning is not None
    assert reasoning["item_type"] == "reasoning_summary"
    assert reasoning["payload"]["delta"] == "展示安全的摘要"


def test_legacy_subagent_tool_is_not_projected_as_a_durable_task() -> None:
    item = project_runtime_item_event(
        {"performative": "tool_call", "metadata": {"tool_name": "task", "tool_call_id": "legacy"}}
    )
    assert item is not None
    assert item["item_type"] == "tool_call"
    assert item["task_uid"] is None
