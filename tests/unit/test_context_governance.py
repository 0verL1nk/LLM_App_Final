from agent.context_governance import build_context_usage_snapshot


def _build_messages(count: int) -> list[dict]:
    messages: list[dict] = []
    for idx in range(count):
        messages.append({"role": "user", "content": f"问题 {idx}：请总结实验设置与结论。"})
        messages.append({"role": "assistant", "content": f"回答 {idx}：实验设置为 A，结论为 B。"})
    return messages


def test_build_context_usage_snapshot_contains_required_keys(monkeypatch):
    monkeypatch.setenv("AGENT_CONTEXT_MAX_INPUT_TOKENS", "10000")
    usage = build_context_usage_snapshot(
        messages=_build_messages(1),
    )
    assert usage["model_window_tokens"] == 10000
    assert "breakdown" in usage
    for key in (
        "system_prompt",
        "custom_agents",
        "tools",
        "messages",
        "summarization_buffer_estimate",
        "free_space",
    ):
        assert key in usage["breakdown"]
