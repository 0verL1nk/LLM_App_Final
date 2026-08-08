from agent.llm_provider import (
    _provider_supports_enable_thinking_flag,
    _provider_supports_reasoning_effort,
)


def test_provider_capability_checks_match_only_the_expected_hostname() -> None:
    assert _provider_supports_reasoning_effort("https://api.openai.com/v1")
    assert _provider_supports_enable_thinking_flag("https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert not _provider_supports_reasoning_effort("https://api.openai.com.attacker.example/v1")
    assert not _provider_supports_enable_thinking_flag("https://attacker.example/dashscope.aliyuncs.com")
