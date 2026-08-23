"""Provider-boundary history hygiene."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.middlewares.builder import build_middleware_list
from agent.middlewares.provider_history_hygiene import (
    ProviderHistoryHygieneMiddleware,
    sanitize_messages_for_provider,
)


def test_failure_artifacts_are_dropped_and_normal_history_kept() -> None:
    sanitized = sanitize_messages_for_provider(
        [
            HumanMessage(content="你好"),
            AIMessage(content="Model call failed after 1 attempt with BadRequestError: 400"),
            AIMessage(content="正常的回答"),
            HumanMessage(content="继续"),
        ]
    )

    assert [type(m).__name__ for m in sanitized] == ["HumanMessage", "AIMessage", "HumanMessage"]
    assert sanitized[1].content == "正常的回答"


def test_consecutive_human_messages_merge_into_one_turn() -> None:
    sanitized = sanitize_messages_for_provider(
        [
            HumanMessage(content="你好"),
            HumanMessage(content="/new"),
            HumanMessage(content="11"),
        ]
    )

    assert len(sanitized) == 1
    assert sanitized[0].content == "你好\n\n/new\n\n11"


def test_alternating_history_passes_through_untouched() -> None:
    messages = [
        HumanMessage(content="第一问"),
        AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "c1"}]),
        ToolMessage(content="tool", tool_call_id="c1"),
        AIMessage(content="第一答"),
        HumanMessage(content="第二问"),
    ]

    assert sanitize_messages_for_provider(messages) == messages


def test_orphaned_tool_messages_are_dropped() -> None:
    sanitized = sanitize_messages_for_provider(
        [
            HumanMessage(content='你好'),
            ToolMessage(content='{}', tool_call_id='orphan-1'),
            ToolMessage(content='{}', tool_call_id='orphan-2'),
            HumanMessage(content='继续'),
        ]
    )

    assert [type(m).__name__ for m in sanitized] == ['HumanMessage']
    assert '你好' in sanitized[0].content and '继续' in sanitized[0].content


def test_matched_tool_call_pairs_survive_including_multiples() -> None:
    ai_with_calls = AIMessage(
        content='',
        tool_calls=[
            {'name': 'search_document', 'args': {'query': 'a'}, 'id': 'call-1'},
            {'name': 'search_document', 'args': {'query': 'b'}, 'id': 'call-2'},
        ],
    )
    sanitized = sanitize_messages_for_provider(
        [
            HumanMessage(content='查一下'),
            ai_with_calls,
            ToolMessage(content='r1', tool_call_id='call-2'),
            ToolMessage(content='r2', tool_call_id='call-1'),
            AIMessage(content='结论'),
        ]
    )

    assert [type(m).__name__ for m in sanitized] == [
        'HumanMessage',
        'AIMessage',
        'ToolMessage',
        'ToolMessage',
        'AIMessage',
    ]


def test_hygiene_middleware_is_wired_into_the_default_stack() -> None:
    class _FakeModel:
        _llm_type = "fake-openai"

    stack = build_middleware_list(model=_FakeModel())

    assert any(isinstance(m, ProviderHistoryHygieneMiddleware) for m in stack)
