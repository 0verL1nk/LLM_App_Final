import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError

from agent import llm_provider as provider
from agent.settings import AgentSettings


def _settings(*, enable_thinking: bool, reasoning_effort: str) -> AgentSettings:
    return AgentSettings(
        openai_compatible_base_url="https://example.com/v1",
        local_models_root="./models",
        local_embedding_model="m1",
        local_embedding_fallback_model="m2",
        local_embedding_cache_dir="./cache",
        local_rerank_cache_dir="./models/flashrank",
        rag_chunk_size=500,
        rag_chunk_overlap=80,
        rag_dense_candidate_k=30,
        rag_sparse_candidate_k=30,
        rag_rrf_candidate_k=40,
        rag_rerank_candidate_k=50,
        rag_top_k=8,
        rag_rerank_enabled=True,
        rag_project_max_chars=300000,
        rag_project_max_chunks=1200,
        rag_project_rerank_enabled=False,
        rag_rerank_model="r1",
        rag_hybrid_enabled=False,
        rag_neighbor_expansion=True,
        rag_neighbor_count=1,
        rag_query_preprocess_enabled=False,
        agent_temperature=0.2,
        agent_enable_thinking=enable_thinking,
        agent_reasoning_effort=reasoning_effort,
        agent_llm_request_timeout=120.0,
    )


def test_build_model_sets_dashscope_enable_thinking(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=True, reasoning_effort="medium"),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="m",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    assert captured["extra_body"] == {"enable_thinking": True}
    assert captured["reasoning_effort"] is None


def test_build_model_sets_openai_reasoning_effort(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=True, reasoning_effort="high"),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="m",
        base_url="https://api.openai.com/v1",
    )

    assert captured["reasoning_effort"] == "high"
    assert captured["extra_body"] is None


def test_build_model_disables_thinking_when_overridden(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=True, reasoning_effort="high"),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="m",
        base_url="https://api.openai.com/v1",
        enable_thinking=False,
        reasoning_effort="",
    )

    assert captured["reasoning_effort"] is None
    assert captured["extra_body"] is None


def test_build_model_sends_explicit_thinking_off_for_dashscope(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=False, reasoning_effort=""),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="m",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    assert captured["extra_body"] == {"enable_thinking": False}


def test_build_model_controls_minimax_m3_thinking_type(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=False, reasoning_effort=""),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="MiniMax-M3",
        base_url="https://api.minimaxi.com/v1",
    )
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="MiniMax-M3",
        base_url="https://api.minimaxi.com/v1",
        enable_thinking=True,
    )
    assert captured["extra_body"] == {"thinking": {"type": "adaptive"}}


def test_build_model_sends_no_thinking_flag_for_minimax_m2(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        provider,
        "load_agent_settings",
        lambda: _settings(enable_thinking=False, reasoning_effort=""),
    )
    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat_openai)

    provider.build_openai_compatible_chat_model(
        api_key="k",
        model_name="MiniMax-M2.1",
        base_url="https://api.minimaxi.com/v1",
    )

    assert captured["extra_body"] is None


class _ReplyModel(BaseModel):
    title: str


class _FakeChatModel:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, _messages):
        return AIMessage(content=self._content)


def test_strip_model_reasoning_removes_wrappers():
    assert (
        provider.strip_model_reasoning('<think>x</think>\n\n{"title": "a"}')
        == '{"title": "a"}'
    )
    assert provider.strip_model_reasoning('```json\n{"title": "a"}\n```') == '{"title": "a"}'
    assert provider.strip_model_reasoning("前言 <think>未闭合的推理") == "前言"
    assert provider.strip_model_reasoning('{"title": "a"}') == '{"title": "a"}'


def test_invoke_structured_model_tolerates_reasoning_prefixes():
    thinking = _FakeChatModel('<think>The user said hi.</think>\n\n{"title": "问候"}')
    assert provider.invoke_structured_model(thinking, _ReplyModel, []).title == "问候"

    fenced = _FakeChatModel('```json\n{"title": "围栏"}\n```')
    assert provider.invoke_structured_model(fenced, _ReplyModel, []).title == "围栏"


def test_invoke_structured_model_injects_schema_instruction():
    captured = {}

    class _CapturingModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content='{"title": "a"}')

    provider.invoke_structured_model(
        _CapturingModel(),
        _ReplyModel,
        [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
        ],
    )

    assert [message["content"] for message in captured["messages"][:2]] == ["s", "u"]
    injected = captured["messages"][-1]
    assert injected["role"] == "system"
    assert "JSON" in injected["content"]
    assert '"title"' in injected["content"]


def test_invoke_structured_model_coerces_bare_text_for_single_field_schema():
    plain = _FakeChatModel("思维导图生成技能测试")
    assert provider.invoke_structured_model(plain, _ReplyModel, []).title == "思维导图生成技能测试"


def test_invoke_structured_model_still_raises_for_unrecoverable_output():
    class _TwoFields(BaseModel):
        title: str
        body: str

    with pytest.raises(ValidationError):
        provider.invoke_structured_model(_FakeChatModel("没有任何花括号的纯文本"), _TwoFields, [])
