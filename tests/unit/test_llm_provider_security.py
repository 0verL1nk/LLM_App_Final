from agent.llm_provider import (
    _provider_supports_reasoning_effort,
    _thinking_extra_body,
)


def test_provider_capability_checks_match_only_the_expected_hostname() -> None:
    assert _provider_supports_reasoning_effort("https://api.openai.com/v1")
    assert _thinking_extra_body(
        "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", False
    ) == {"enable_thinking": False}
    assert _thinking_extra_body(
        "https://api.minimaxi.com/v1", "MiniMax-M3", False
    ) == {"thinking": {"type": "disabled"}}
    assert not _provider_supports_reasoning_effort("https://api.openai.com.attacker.example/v1")
    assert _thinking_extra_body(
        "https://attacker.example/dashscope.aliyuncs.com", "qwen-plus", False
    ) is None
    assert _thinking_extra_body(
        "https://attacker.example/api.minimaxi.com", "MiniMax-M3", False
    ) is None
