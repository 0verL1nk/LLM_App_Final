from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agent.domain.human_request import (
    build_human_reply_prompt,
    extract_answered_request_ids,
    extract_human_requests,
)
from agent.subagent.loader import load_subagent_definitions


def test_human_request_round_trip_keeps_request_identity() -> None:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "approval-1",
                    "name": "ask_human",
                    "args": {
                        "question": "是否允许外部检索？",
                        "context": "本地文档证据不足",
                        "urgency": "high",
                    },
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            name="ask_human",
            tool_call_id="approval-1",
            content='{"type":"ask_human","question":"是否允许外部检索？","context":"本地文档证据不足","urgency":"high"}',
        ),
    ]

    requests = extract_human_requests(messages)

    assert requests == [
        {
            "request_id": "approval-1",
            "question": "是否允许外部检索？",
            "context": "本地文档证据不足",
            "urgency": "high",
        }
    ]
    prompt = build_human_reply_prompt(requests[0], "允许")
    assert "Request ID: approval-1" in prompt
    assert "Human response: 允许" in prompt
    assert extract_answered_request_ids([{"role": "user", "content": prompt}]) == {
        "approval-1"
    }


def test_invalid_subagent_config_fails_fast(tmp_path: Path) -> None:
    config_dir = tmp_path / "broken"
    config_dir.mkdir()
    (config_dir / "agent.md").write_text("not front matter", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid subagent config"):
        load_subagent_definitions(tmp_path)
