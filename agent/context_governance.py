import logging
import math
import os
from functools import lru_cache
from typing import Any

from .paper_prompt import PAPER_QA_SYSTEM_PROMPT
from .subagent.loader import load_subagent_definitions

logger = logging.getLogger(__name__)



def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value.strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value.strip())
    except Exception:
        return default


def model_context_window_tokens() -> int:
    return max(2048, _env_int("AGENT_CONTEXT_MAX_INPUT_TOKENS", 200_000))


def reserved_output_tokens() -> int:
    return max(512, _env_int("AGENT_CONTEXT_RESERVED_OUTPUT_TOKENS", 16_000))


def compact_trigger_ratio() -> float:
    return min(0.95, max(0.20, _env_float("AGENT_AUTO_COMPACT_TRIGGER_RATIO", 0.55)))




@lru_cache(maxsize=8)
def _resolve_encoding(model_name: str):
    try:
        import tiktoken
    except Exception:
        return None
    normalized = model_name.strip() if isinstance(model_name, str) else ""
    try:
        if normalized:
            return tiktoken.encoding_for_model(normalized)
    except Exception:
        pass
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    if not isinstance(text, str) or not text:
        return 0
    tokenizer_model = os.getenv("AGENT_TOKENIZER_MODEL", "").strip()
    encoding = _resolve_encoding(tokenizer_model)
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    non_ascii_chars = len(text) - ascii_chars
    # Display-only fallback when the tokenizer is unavailable. This estimate is
    # never used for semantic routing or memory decisions.
    return max(1, math.ceil(ascii_chars / 4.0) + math.ceil(non_ascii_chars / 1.6))


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
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
    return str(content)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        total += estimate_tokens(_message_text(message)) + 8
    return total


def _estimate_tools_tokens(tool_specs: list[dict[str, str]] | None = None) -> int:
    if not isinstance(tool_specs, list):
        return 0
    total = 0
    for item in tool_specs:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        args_schema = str(item.get("args_schema") or "").strip()
        if not (name or description or args_schema):
            continue
        total += estimate_tokens(f"{name}\n{description}\n{args_schema}")
    return total


def build_context_usage_snapshot(
    *,
    messages: list[dict[str, Any]],
    tool_specs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    max_input = model_context_window_tokens()
    reserve_output = reserved_output_tokens()

    system_tokens = estimate_tokens(PAPER_QA_SYSTEM_PROMPT)

    # 统计 subagent 元信息的 token 数
    custom_agents_tokens = 0
    try:
        for definition in load_subagent_definitions():
            custom_agents_tokens += estimate_tokens(definition.name)
            custom_agents_tokens += estimate_tokens(definition.description)
    except (OSError, ValueError) as exc:
        logger.warning("Unable to account for subagent prompt tokens: %s", exc)
        custom_agents_tokens = 0
    tools_tokens = _estimate_tools_tokens(tool_specs)
    messages_tokens = estimate_message_tokens(messages)
    tools_count = len(tool_specs) if isinstance(tool_specs, list) else 0
    used_tokens = (
        system_tokens
        + custom_agents_tokens
        + tools_tokens
        + messages_tokens
    )
    summarization_buffer_estimate = max(
        0,
        int(max_input * compact_trigger_ratio()) - used_tokens,
    )
    free_tokens = max(0, max_input - reserve_output - used_tokens)
    total_visible = used_tokens + summarization_buffer_estimate + free_tokens
    if total_visible <= 0:
        total_visible = 1

    def _pct(value: int) -> float:
        return round((value / total_visible) * 100.0, 1)

    def _ratio(value: int) -> float:
        return (value / total_visible) * 100.0

    context_order = [
        ("system_prompt", "Primary agent prompt", system_tokens),
        ("custom_agents", "Subagent manifests", custom_agents_tokens),
        ("tools", "Tools", tools_tokens),
        ("messages", "Messages", messages_tokens),
        ("free_space", "Free space", free_tokens),
        (
            "summarization_buffer_estimate",
            "Summarization trigger buffer (estimated)",
            summarization_buffer_estimate,
        ),
    ]
    context_segments: list[dict[str, Any]] = []
    cursor = 0.0
    for key, label, tokens in context_order:
        ratio = max(0.0, _ratio(tokens))
        start = cursor
        end = min(100.0, start + ratio)
        context_segments.append(
            {
                "key": key,
                "label": label,
                "tokens": tokens,
                "pct": round(ratio, 2),
                "start_pct": round(start, 2),
                "end_pct": round(end, 2),
            }
        )
        cursor = end

    return {
        "model_window_tokens": max_input,
        "reserved_output_tokens": reserve_output,
        "used_tokens": used_tokens,
        "free_tokens": free_tokens,
        "summarization_buffer_estimate": summarization_buffer_estimate,
        "tools_count": tools_count,
        "primary_agent_name": "react_agent",
        "context_view_scope": "application-visible estimate",
        "context_segments": context_segments,
        "breakdown": {
            "system_prompt": {"tokens": system_tokens, "pct": _pct(system_tokens)},
            "custom_agents": {"tokens": custom_agents_tokens, "pct": _pct(custom_agents_tokens)},
            "tools": {"tokens": tools_tokens, "pct": _pct(tools_tokens)},
            "messages": {"tokens": messages_tokens, "pct": _pct(messages_tokens)},
            "free_space": {"tokens": free_tokens, "pct": _pct(free_tokens)},
            "summarization_buffer_estimate": {
                "tokens": summarization_buffer_estimate,
                "pct": _pct(summarization_buffer_estimate),
            },
        },
    }
