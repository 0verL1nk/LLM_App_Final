from langchain_core.messages import AIMessage

from agent.application import session_suggestions


class _SuggestionsModel:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, _messages):
        return AIMessage(content=self._content)


def _configure(monkeypatch, model=None, key="key", name="model") -> None:
    monkeypatch.setattr(session_suggestions, "read_api_key_for_user", lambda **_kwargs: key)
    monkeypatch.setattr(session_suggestions, "read_model_name_for_user", lambda **_kwargs: name)
    monkeypatch.setattr(session_suggestions, "read_base_url_for_user", lambda **_kwargs: "")
    monkeypatch.setattr(
        session_suggestions,
        "build_openai_compatible_chat_model",
        lambda **_kwargs: model,
    )


def test_suggestions_tolerate_reasoning_wrapped_json(monkeypatch) -> None:
    model = _SuggestionsModel(
        '<think>基于对话,用户在对比检索策略。</think>\n\n{"items": ["对比两种检索策略的召回率", " 总结当前证据缺口"]}'
    )
    _configure(monkeypatch, model=model)

    items = session_suggestions.generate_session_suggestions(
        user_uuid="u1",
        project_uid="p1",
        session_uid="s1",
        messages=[{"role": "user", "content": "帮我比较检索策略"}],
        document_names=["检索综述.pdf"],
    )

    assert items == ["对比两种检索策略的召回率", "总结当前证据缺口"]


def test_suggestions_return_empty_without_configured_model(monkeypatch) -> None:
    _configure(monkeypatch, model=None, key="", name="")

    assert session_suggestions.generate_session_suggestions(
        user_uuid="u1",
        project_uid="p1",
        session_uid="s1",
        messages=[],
        document_names=[],
    ) == []


def test_suggestions_swallow_model_failures(monkeypatch) -> None:
    class _ExplodingModel:
        def invoke(self, _messages):
            raise RuntimeError("provider down")

    _configure(monkeypatch, model=_ExplodingModel())

    assert session_suggestions.generate_session_suggestions(
        user_uuid="u1",
        project_uid="p1",
        session_uid="s1",
        messages=[],
        document_names=[],
    ) == []
