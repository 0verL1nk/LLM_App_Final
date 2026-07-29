from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.middlewares.mindmap_format import MindmapFormatMiddleware


def _mindmap_request_messages() -> list:
    return [
        HumanMessage(content="请生成思维导图"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "skill-1",
                    "name": "use_skill",
                    "args": {"skill_name": "mindmap", "task": "生成思维导图"},
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="Skill: mindmap", tool_call_id="skill-1", name="use_skill"),
    ]


def test_mindmap_format_middleware_retries_invalid_mermaid_output() -> None:
    middleware = MindmapFormatMiddleware()
    requests: list[ModelRequest[None]] = []

    def _handler(request: ModelRequest[None]) -> ModelResponse[None]:
        requests.append(request)
        if len(requests) == 1:
            return ModelResponse(
                result=[
                    AIMessage(
                        content="## 思维导图\n```mermaid\nmindmap\n  root((Seed-TTS))\n```"
                    )
                ]
            )
        return ModelResponse(
            result=[
                AIMessage(
                    content='{"version":"v0.9","createSurface":{"surfaceId":"mindmap-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}\n{"version":"v0.9","updateComponents":{"surfaceId":"mindmap-1","components":[{"id":"root","component":"Mindmap","data":{"path":"/mindmap"}}]}}\n{"version":"v0.9","updateDataModel":{"surfaceId":"mindmap-1","path":"/mindmap","value":{"label":"Seed-TTS","children":[]}}}'
                )
            ]
        )

    response = middleware.wrap_model_call(
        ModelRequest(
            model="llm",  # type: ignore[arg-type]
            messages=_mindmap_request_messages(),
            system_message=SystemMessage(content="sys"),
        ),
        _handler,
    )

    assert len(requests) == 2
    assert '"createSurface"' in str(response.result[0].content)
    retry_messages = requests[1].messages
    assert isinstance(retry_messages[-1], HumanMessage)
    assert "A2UI" in retry_messages[-1].content
    assert "v0.9" in retry_messages[-1].content


def test_mindmap_format_middleware_passes_valid_tagged_json_without_retry() -> None:
    middleware = MindmapFormatMiddleware()
    calls = {"count": 0}

    def _handler(request: ModelRequest[None]) -> ModelResponse[None]:
        calls["count"] += 1
        return ModelResponse(
            result=[AIMessage(content='{"version":"v0.9","createSurface":{"surfaceId":"mindmap-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}\n{"version":"v0.9","updateComponents":{"surfaceId":"mindmap-1","components":[{"id":"root","component":"Mindmap","data":{"path":"/mindmap"}}]}}\n{"version":"v0.9","updateDataModel":{"surfaceId":"mindmap-1","path":"/mindmap","value":{"label":"主题","children":[]}}}')]
        )

    response = middleware.wrap_model_call(
        ModelRequest(
            model="llm",  # type: ignore[arg-type]
            messages=_mindmap_request_messages(),
            system_message=SystemMessage(content="sys"),
        ),
        _handler,
    )

    assert calls["count"] == 1
    assert '"updateDataModel"' in str(response.result[0].content)


def test_mindmap_format_middleware_returns_failure_message_after_retry_exhausted() -> None:
    middleware = MindmapFormatMiddleware()
    calls = {"count": 0}

    def _handler(request: ModelRequest[None]) -> ModelResponse[None]:
        calls["count"] += 1
        return ModelResponse(result=[AIMessage(content="```mermaid\nmindmap\n  root((X))\n```")])

    response = middleware.wrap_model_call(
        ModelRequest(
            model="llm",  # type: ignore[arg-type]
            messages=_mindmap_request_messages(),
            system_message=SystemMessage(content="sys"),
        ),
        _handler,
    )

    assert calls["count"] == 2
    assert "思维导图" in str(response.result[0].content)


def test_mindmap_format_middleware_does_not_retry_regular_text_output() -> None:
    middleware = MindmapFormatMiddleware()
    calls = {"count": 0}

    def _handler(request: ModelRequest[None]) -> ModelResponse[None]:
        calls["count"] += 1
        return ModelResponse(result=[AIMessage(content="这是普通总结，不是思维导图。")])

    response = middleware.wrap_model_call(
        ModelRequest(
            model="llm",  # type: ignore[arg-type]
            messages=[HumanMessage(content="请总结一下论文")],
            system_message=SystemMessage(content="sys"),
        ),
        _handler,
    )

    assert calls["count"] == 1
    assert response.result[0].content == "这是普通总结，不是思维导图。"
