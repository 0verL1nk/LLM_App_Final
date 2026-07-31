"""Mindmap output format guard middleware."""

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from ..application.a2ui_mindmap import parse_a2ui_mindmap_jsonl

logger = logging.getLogger(__name__)

_MAX_REWRITE_ATTEMPTS = 1
_MAX_BAD_OUTPUT_PREVIEW = 600
_RETRY_PROMPT = """你刚才的思维导图输出格式不符合要求，必须重写。

错误要求说明：
- 必须只输出三行 A2UI v0.9 JSONL surface，不要任何 XML/HTML tag
- catalogId 必须是 `https://papersage.local/a2ui/catalogs/mindmap-v1.json`，只允许 `Mindmap` 组件与 `/mindmap` 数据
- 禁止输出 Mermaid、HTML、JavaScript、SVG、CSS 或 Markdown 代码块

正确格式示例：
{{"version":"v0.9","createSurface":{{"surfaceId":"mindmap-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}}}
{{"version":"v0.9","updateComponents":{{"surfaceId":"mindmap-1","components":[{{"id":"root","component":"Mindmap","data":{{"path":"/mindmap"}}}}]}}}}
{{"version":"v0.9","updateDataModel":{{"surfaceId":"mindmap-1","path":"/mindmap","value":{{"label":"主题","children":[]}}}}}}

你刚才的错误输出片段：
{bad_output}

请基于同一内容立即重写，并且只输出合法的 A2UI JSONL 内容。"""

_FINAL_FAILURE_MESSAGE = (
    "思维导图暂时无法生成，请重试。"
)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    tool_calls = getattr(message, "tool_calls", None)
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []
    return [item for item in tool_calls if isinstance(item, dict)]


def _extract_use_skill_name(tool_call: dict[str, Any]) -> str:
    name = str(tool_call.get("name") or "").strip()
    if name != "use_skill":
        return ""
    args = tool_call.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return ""
    if not isinstance(args, dict):
        return ""
    return str(args.get("skill_name") or "").strip().lower()


def _expects_mindmap_response(messages: list[Any]) -> bool:
    for message in messages:
        role = str(getattr(message, "type", getattr(message, "role", "")) or "").strip().lower()
        content = _content_to_text(getattr(message, "content", ""))
        if isinstance(message, dict):
            role = str(message.get("type") or message.get("role") or "").strip().lower()
            content = _content_to_text(message.get("content", ""))
        for tool_call in _message_tool_calls(message):
            if _extract_use_skill_name(tool_call) == "mindmap":
                return True
        if role == "tool":
            name = str(getattr(message, "name", "") or "")
            if isinstance(message, dict):
                name = str(message.get("name") or "")
            if name == "use_skill" and "Skill: mindmap" in content:
                return True
    return False


def _extract_last_ai_message(messages: list[Any]) -> AIMessage | None:
    for item in reversed(messages):
        if isinstance(item, AIMessage):
            return item
    return None


def _parse_strict_mindmap_payload(text: str) -> dict[str, Any] | None:
    return parse_a2ui_mindmap_jsonl(text)


def _preview_bad_output(text: str) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= _MAX_BAD_OUTPUT_PREVIEW:
        return collapsed
    return f"{collapsed[:_MAX_BAD_OUTPUT_PREVIEW]}..."


class MindmapFormatMiddleware(AgentMiddleware):
    """Retry mindmap responses until they satisfy the strict tagged JSON contract."""

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        current_request = request
        for attempt in range(_MAX_REWRITE_ATTEMPTS + 1):
            response = handler(current_request)
            ai_message = _extract_last_ai_message(list(response.result or []))
            if ai_message is None:
                return response
            if getattr(ai_message, "tool_calls", None):
                return response

            answer = _content_to_text(ai_message.content)
            if _parse_strict_mindmap_payload(answer) is not None:
                return response
            if not _expects_mindmap_response(list(current_request.messages or [])):
                return response

            if attempt >= _MAX_REWRITE_ATTEMPTS:
                logger.warning("mindmap format validation failed after retry: %s", _preview_bad_output(answer))
                return ModelResponse(result=[AIMessage(content=_FINAL_FAILURE_MESSAGE)])

            logger.info("mindmap format validation failed, requesting rewrite: %s", _preview_bad_output(answer))
            rewrite_prompt = HumanMessage(
                content=_RETRY_PROMPT.format(bad_output=_preview_bad_output(answer) or "(empty)")
            )
            current_request = current_request.override(
                messages=[*list(current_request.messages or []), ai_message, rewrite_prompt]
            )

        return handler(current_request)


mindmap_format_middleware = MindmapFormatMiddleware()

__all__ = [
    "MindmapFormatMiddleware",
    "mindmap_format_middleware",
]
