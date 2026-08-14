import json

from agent.application.continuation_messages import build_continuation_tool_message


def test_continuation_message_carries_merge_only_when_provided() -> None:
    message = build_continuation_tool_message(
        {"task_uid": "task-1", "role": "researcher", "status": "completed", "tool_call_id": "call-1", "packet": {"summary": "Found evidence"}},
        evidence_merge={"conflicts": []},
    )

    assert message.name == "delegate_task"
    assert message.tool_call_id == "call-1"
    assert json.loads(str(message.content))["evidence_merge"] == {"conflicts": []}
