from agent.application.turn_engine import (
    _maybe_to_dict,
    build_search_document_fn,
    execute_turn_core,
)


def test_build_search_document_fn_joins_evidence_text():
    search_fn = build_search_document_fn(
        lambda _query: {"evidences": [{"text": "a"}, {"text": "b"}, {"text": "  "}]}
    )
    assert search_fn("q") == "a\nb"


def test_execute_turn_core_with_injected_executor_replaces_evidence():
    from unittest.mock import Mock

    events = []
    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            Mock(
                content="结论 <evidence>c1|p1|o0-10</evidence>",
                tool_calls=[{"name": "search_document", "args": {"query": "test"}}],
            )
        ]
    }

    result = execute_turn_core(
        prompt="请给结论",
        leader_agent=mock_agent,
        leader_runtime_config={},
        search_document_evidence_fn=lambda _query: {
            "evidences": [{"chunk_id": "c1", "text": "证据文本", "page_no": 1}]
        },
        on_event=lambda item: events.append(item),
    )

    assert result["used_document_rag"] is True
    assert result["evidence_items"]
    assert len(result["evidence_items"]) == 1
    assert result["evidence_items"][0]["chunk_id"] == "c1"
    assert result["retrieved_evidence_items"][0]["chunk_id"] == "c1"


def test_execute_turn_core_streams_answer_deltas_without_reinvoking() -> None:
    from types import SimpleNamespace

    class _StreamingAgent:
        def invoke(self, *_args, **_kwargs):
            raise AssertionError("streaming run must not invoke the agent twice")

        def stream(self, *_args, **_kwargs):
            yield {"type": "messages", "data": (SimpleNamespace(content="流式"), {"langgraph_node": "model"})}
            yield {"type": "messages", "data": (SimpleNamespace(content="回答"), {"langgraph_node": "model"})}
            yield {"type": "values", "data": {"messages": [SimpleNamespace(content="流式回答", tool_calls=[])]}}

    events: list[dict[str, object]] = []
    result = execute_turn_core(
        prompt="请回答",
        leader_agent=_StreamingAgent(),
        leader_runtime_config={},
        on_event=events.append,
    )

    assert result["answer"] == "流式回答"
    assert [event["content"] for event in events] == ["流式", "回答"]


def test_execute_turn_core_keeps_markdown_answer_with_tool_requested_surface() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="结论来自文档。<evidence>chunk-1|p1|o0-10</evidence>",
                tool_calls=[
                    {"name": "search_document", "args": {"query": "方法"}},
                    {
                        "name": "present_research_surface",
                        "args": {
                            "title": "方法结构",
                            "root": {
                                "label": "论文",
                                "citation_ids": ["chunk-1"],
                                "children": [],
                            },
                        },
                    },
                ],
            )
        ]
    }

    result = execute_turn_core(
        prompt="梳理方法",
        leader_agent=mock_agent,
        leader_runtime_config={},
        search_document_evidence_fn=lambda _query: {
            "evidences": [{"chunk_id": "chunk-1", "text": "证据文本", "page_no": 1}]
        },
    )

    assert result["answer"].startswith("结论来自文档")
    assert result["a2ui_surface"]["title"] == "方法结构"
    assert result["a2ui_surface"]["mindmap"]["citation_ids"] == ["chunk-1"]


def test_execute_turn_core_without_document_rag_skips_evidence():
    from unittest.mock import Mock

    called = {"evidence": 0}

    def _evidence_fn(_query: str):
        called["evidence"] += 1
        return {"evidences": [{"chunk_id": "c2", "text": "x"}]}

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            Mock(
                content='{"name":"主题","children":[]}',
                tool_calls=[{"name": "search_web", "args": {"query": "test"}}],
            )
        ]
    }

    result = execute_turn_core(
        prompt="最新进展",
        leader_agent=mock_agent,
        leader_runtime_config={},
        search_document_evidence_fn=_evidence_fn,
    )

    assert called["evidence"] == 0
    assert result["used_document_rag"] is False
    assert result["evidence_items"] == []
    assert result["mindmap_data"] is None or isinstance(result["mindmap_data"], dict)


def test_execute_turn_core_uses_search_document_tool_result_evidence_without_reretrieval():
    from types import SimpleNamespace
    from unittest.mock import Mock

    called = {"evidence": 0}

    def _evidence_fn(_query: str):
        called["evidence"] += 1
        return {"evidences": [{"chunk_id": "other_chunk", "text": "不会被使用"}]}

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "search_document", "args": {"query": "rag"}}],
            ),
            {
                "role": "tool",
                "name": "search_document",
                "content": (
                    '{"evidences": ['
                    '{"chunk_id": "arxiv:2005.11401:chunk_11", "text": "证据文本", "page_no": 1, "offset_start": 0, "offset_end": 10}'
                    "]} "
                ),
            },
            SimpleNamespace(
                content="结论 <evidence>arxiv:2005.11401:chunk_11|p1|o0-10</evidence>",
                tool_calls=[],
            ),
        ]
    }

    result = execute_turn_core(
        prompt="请概括 RAG 核心结论",
        leader_agent=mock_agent,
        leader_runtime_config={},
        search_document_evidence_fn=_evidence_fn,
    )

    assert called["evidence"] == 0
    assert result["used_document_rag"] is True
    assert result["evidence_items"]
    assert result["evidence_items"][0]["chunk_id"] == "arxiv:2005.11401:chunk_11"


def test_execute_turn_core_matches_plain_doc_uid_citation_to_tool_evidence() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "search_document", "args": {"query": "rag"}}],
            ),
            {
                "role": "tool",
                "name": "search_document",
                "content": (
                    '{"evidences": ['
                    '{"doc_uid": "arxiv:2005.11401", "chunk_id": "arxiv:2005.11401:chunk_11", "text": "证据文本", "page_no": 1, "offset_start": 0, "offset_end": 10}'
                    "]} "
                ),
            },
            SimpleNamespace(
                content="结论引用 arxiv:2005.11401|p1|o0-10，建议优先采用标准 RAG。",
                tool_calls=[],
            ),
        ]
    }

    result = execute_turn_core(
        prompt="请概括 RAG 核心结论",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    assert result["used_document_rag"] is True
    assert result["evidence_items"]
    assert result["evidence_items"][0]["chunk_id"] == "arxiv:2005.11401:chunk_11"


def test_execute_turn_core_normalizes_malformed_evidence_tags() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "search_document", "args": {"query": "self-rag"}}],
            ),
            {
                "role": "tool",
                "name": "search_document",
                "content": (
                    '{"evidences": ['
                    '{"chunk_id": "arxiv:2310.11511:chunk_73", "text": "证据文本", "page_no": 1, "offset_start": 966, "offset_end": 1450}'
                    "]} "
                ),
            },
            SimpleNamespace(
                content=(
                    "结论【evidence】arxiv:2310.11511:chunk_73|p1|o966-1450</evidence>"
                ),
                tool_calls=[],
            ),
        ]
    }

    result = execute_turn_core(
        prompt="请判断是否应暂缓 Self-RAG",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    assert result["answer"] == "结论<evidence>arxiv:2310.11511:chunk_73|p1|o966-1450</evidence>"
    assert result["used_document_rag"] is True
    assert len(result["evidence_items"]) == 1
    assert result["evidence_items"][0]["chunk_id"] == "arxiv:2310.11511:chunk_73"


def test_execute_turn_core_matches_inline_bracket_chunk_reference_with_pnull() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "search_document", "args": {"query": "self-rag latency"}}],
            ),
            {
                "role": "tool",
                "name": "search_document",
                "content": (
                    '{"evidences": ['
                    '{"chunk_id": "arxiv:2310.11511:chunk_106", "doc_uid": "arxiv:2310.11511", "text": "证据文本", "page_no": null, "offset_start": 15125, "offset_end": 15578}'
                    "]} "
                ),
            },
            SimpleNamespace(
                content=(
                    "结论【arxiv:2310.11511:chunk_106|pnull|o15125-15578】应暂缓 Self-RAG。"
                ),
                tool_calls=[],
            ),
        ]
    }

    result = execute_turn_core(
        prompt="请判断是否应暂缓 Self-RAG",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    assert result["used_document_rag"] is True
    assert len(result["evidence_items"]) == 1
    assert result["evidence_items"][0]["chunk_id"] == "arxiv:2310.11511:chunk_106"


def test_execute_turn_core_does_not_count_tool_result_evidence_without_answer_citations():
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "search_document", "args": {"query": "rag"}}],
            ),
            {
                "role": "tool",
                "name": "search_document",
                "content": (
                    '{"evidences": ['
                    '{"chunk_id": "arxiv:2005.11401:chunk_11", "text": "证据文本", "page_no": 1}'
                    "]} "
                ),
            },
            SimpleNamespace(
                content="这是没有证据标签的总结。",
                tool_calls=[],
            ),
        ]
    }

    result = execute_turn_core(
        prompt="请概括 RAG 核心结论",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    assert result["used_document_rag"] is True
    assert result["evidence_items"] == []


def test_execute_turn_core_infers_final_phase_from_answer_without_final_event():
    from types import SimpleNamespace

    class _Agent:
        def invoke(self, payload, config=None):
            assert payload["messages"][0]["content"] == "请总结"
            if isinstance(config, dict):
                configurable = config.get("configurable")
                if isinstance(configurable, dict):
                    on_event = configurable.get("on_event")
                    if callable(on_event):
                        on_event(
                            {
                                "sender": "leader",
                                "receiver": "leader",
                                "performative": "unknown_internal_phase",
                                "content": "处理中",
                            }
                        )
            return {
                "messages": [
                    SimpleNamespace(
                        content="最终回答",
                        tool_calls=[],
                    )
                ]
            }

    result = execute_turn_core(
        prompt="请总结",
        leader_agent=_Agent(),
        leader_runtime_config={},
    )

    assert result["answer"] == "最终回答"
    assert result["phase_path"].endswith("输出最终答案")


def test_execute_turn_core_sends_raw_user_prompt_and_turn_context() -> None:
    captured: dict[str, object] = {}

    class _Agent:
        def invoke(self, payload, config=None):
            captured["payload"] = payload
            captured["config"] = config
            return {"messages": [{"role": "assistant", "content": "ok"}]}

    result = execute_turn_core(
        prompt="真实用户问题",
        turn_context={
            "response_language": "en",
            "memory_items": [{"memory_type": "semantic", "content": "prefers concise answers"}],
        },
        leader_agent=_Agent(),
        leader_runtime_config={"configurable": {"thread_id": "tid"}},
    )

    assert result["answer"] == "ok"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["messages"] == [{"role": "user", "content": "真实用户问题"}]
    config = captured["config"]
    assert isinstance(config, dict)
    assert config["configurable"]["thread_id"] == "tid"
    assert config["configurable"]["turn_context"] == {
        "response_language": "en",
        "memory_items": [{"memory_type": "semantic", "content": "prefers concise answers"}],
    }


def test_execute_turn_core_logs_final_answer(caplog) -> None:
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            Mock(
                content="最终回答内容",
                tool_calls=[],
            )
        ]
    }

    with caplog.at_level("INFO"):
        result = execute_turn_core(
            prompt="请总结",
            leader_agent=mock_agent,
            leader_runtime_config={},
        )

    assert result["answer"] == "最终回答内容"
    assert "TURN_FINAL_ANSWER: 最终回答内容" in caplog.text


def test_maybe_to_dict_handles_none_and_noncallable_values():
    assert _maybe_to_dict(None) is None
    assert _maybe_to_dict({"x": 1}) == {"x": 1}

    class _Payload:
        def to_dict(self):
            return {"ok": True}

    assert _maybe_to_dict(_Payload()) == {"ok": True}


def test_execute_turn_core_exposes_observed_delegation_and_scheduler_state():
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "task-1",
                        "name": "task",
                        "args": {
                            "subagent_type": "researcher",
                            "description": "检索证据",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "name": "task",
                "tool_call_id": "task-1",
                "content": "证据结果",
            },
            {"role": "assistant", "content": "请先执行 todo", "tool_calls": []},
        ],
        "todo_scheduler_hint": {
            "ready_todo_ids": ["todo-2"],
            "blocked_todo_ids": [],
            "completed_todo_ids": ["todo-1"],
            "in_progress_todo_ids": [],
        },
        "todos": [
            {
                "id": "todo-1",
                "content": "检索证据",
                "status": "completed",
                "depends_on": [],
            },
            {
                "id": "todo-2",
                "content": "整理结论",
                "status": "ready",
                "depends_on": ["todo-1"],
            },
        ],
    }

    result = execute_turn_core(
        prompt="请协作完成分析",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    assert result["policy_decision"]["delegation_enabled"] is True
    assert result["todo_scheduler_hint"]["ready_todo_ids"] == ["todo-2"]
    assert result["delegation_execution"]["enabled"] is True
    assert result["delegation_execution"]["roles"] == ["researcher"]
    assert result["delegation_execution"]["tasks"][0]["status"] == "completed"
    assert result["delegation_rounds"] == 1
    assert any(
        event["performative"] == "delegate_task" for event in result["trace_payload"]
    )
