from agent.application.turn_engine import execute_turn_core


def test_execute_turn_core_keeps_markdown_answer_with_inline_ui_surface() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content='结论来自文档。<evidence>chunk-1|p1|o0-10</evidence>\n<ui type="research-map"><map title="方法结构"><node label="论文"><evidence ref="chunk-1" /></node></map></ui>',
                tool_calls=[
                    {"name": "search_document", "args": {"query": "方法"}},
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
    component_parts = [
        part for part in result["response_parts"] if part.get("type") == "component"
    ]
    assert len(component_parts) == 1
    assert component_parts[0]["component"] == "research-map"
    assert component_parts[0]["state"] == "ready"
    assert '<map title="方法结构">' in component_parts[0]["xml"]
    assert "a2ui_surface" not in result
    assert "a2ui_surfaces" not in result



def test_execute_turn_core_keeps_error_component_for_unterminated_fragment() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                content='正文在前\n<ui type="research-map"><map title="半成品"><node label="x" />',
            )
        ]
    }

    result = execute_turn_core(
        prompt="画图",
        leader_agent=mock_agent,
        leader_runtime_config={},
    )

    component_parts = [
        part for part in result["response_parts"] if part.get("type") == "component"
    ]
    assert len(component_parts) == 1
    assert component_parts[0]["state"] == "error"
    assert "component-0" == component_parts[0]["id"]
    # The salvaged fragment text flows back into the visible answer.
    assert "正文在前" in result["answer"]
