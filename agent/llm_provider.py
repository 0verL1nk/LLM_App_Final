from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr, ValidationError

from .settings import load_agent_settings

_REASONING_BLOCK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_CODE_FENCE_PATTERN = re.compile(r"```[a-zA-Z0-9_-]*\s*(.*?)\s*```", re.DOTALL)


def strip_model_reasoning(text: str) -> str:
    """Drop <think> reasoning blocks and code fences wrapped around JSON.

    OpenAI-compatible providers such as DashScope emit reasoning text before
    the JSON payload, which otherwise breaks structured-output parsing.
    """
    cleaned = _REASONING_BLOCK_PATTERN.sub("", text)
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>", 1)[0]
    fenced = _CODE_FENCE_PATTERN.search(cleaned)
    if fenced:
        cleaned = fenced.group(1)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return cleaned.strip()


def _coerce_bare_text(schema: type[BaseModel], text: str) -> BaseModel | None:
    """Rescue single-field schemas when the model answers with the value alone.

    Small OpenAI-compatible models sometimes reply with the bare field value
    (e.g. just the title) even when asked for JSON.
    """
    if "{" in text or not str(text or "").strip():
        return None
    field_names = list(schema.model_fields)
    if len(field_names) != 1:
        return None
    try:
        return schema.model_validate({field_names[0]: text.strip()})
    except ValidationError:
        return None


def invoke_structured_model(
    llm: Any,
    schema: type[BaseModel],
    messages: list[dict[str, str]],
) -> BaseModel:
    """Invoke a chat model and validate its sanitized JSON against ``schema``.

    Long judge reasonings occasionally produce malformed JSON, so one fresh
    retry is taken before surfacing the validation error.
    """
    schema_instruction = {
        "role": "system",
        "content": (
            "Respond with exactly one JSON object and no other text. It must "
            "conform to this JSON schema:\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        ),
    }
    last_error: Exception | None = None
    for _attempt in range(2):
        response = llm.invoke([*messages, schema_instruction])
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        cleaned = strip_model_reasoning(content)
        try:
            return schema.model_validate_json(cleaned)
        except ValidationError as exc:
            last_error = exc
            coerced = _coerce_bare_text(schema, cleaned)
            if coerced is not None:
                return coerced
    raise last_error if last_error is not None else RuntimeError("structured model call failed")


def _get_model_max_input_tokens(model_name: str) -> int:
    """根据模型名称返回最大输入token数,默认200,000"""
    # 统一默认值为 200,000
    return 200000


def _provider_supports_reasoning_effort(base_url: str) -> bool:
    return _provider_host(base_url) == "api.openai.com"


OPENAI_COMPATIBLE_MAX_RETRIES = 6


def _thinking_extra_body(
    base_url: str,
    model_name: str,
    enable_thinking: bool,
) -> dict[str, object] | None:
    """Map the thinking switch to provider-level flags, sent explicitly for both
    on and off. Providers without a known flag get ``None`` (no guessing).

    - DashScope hybrid models read ``enable_thinking``; an explicit ``False`` is
      required to keep Qwen-style models from thinking by default.
    - MiniMax M3 reads ``thinking.type`` (``adaptive``/``disabled``; ``enabled``
      is rejected with a 400). M2.x cannot disable thinking, so no flag is sent
      for non-M3 MiniMax models.
    """
    host = _provider_host(base_url)
    if host == "dashscope.aliyuncs.com":
        return {"enable_thinking": enable_thinking}
    if host in {"api.minimaxi.com", "api.minimax.io"}:
        if model_name.strip().upper().startswith("MINIMAX-M3"):
            return {"thinking": {"type": "adaptive" if enable_thinking else "disabled"}}
        return None
    return None


def _provider_host(base_url: str) -> str:
    """Return a normalized provider hostname without trusting URL substrings."""
    try:
        return (urlsplit(base_url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def build_openai_compatible_chat_model(
    api_key: str,
    model_name: str,
    temperature: float | None = None,
    base_url: str | None = None,
    enable_thinking: bool | None = None,
    reasoning_effort: str | None = None,
    timeout: float | None = None,
) -> ChatOpenAI:
    settings = load_agent_settings()
    resolved_temperature = (
        settings.agent_temperature if temperature is None else temperature
    )
    resolved_base_url = (
        settings.openai_compatible_base_url if not base_url else base_url
    )
    resolved_enable_thinking = (
        settings.agent_enable_thinking if enable_thinking is None else enable_thinking
    )
    resolved_reasoning_effort = (
        settings.agent_reasoning_effort
        if reasoning_effort is None
        else reasoning_effort.strip()
    )
    resolved_timeout = timeout if timeout is not None else settings.agent_llm_request_timeout

    resolved_reasoning: str | None = None
    resolved_extra_body: dict[str, object] | None = _thinking_extra_body(
        resolved_base_url,
        model_name,
        resolved_enable_thinking,
    )
    if resolved_enable_thinking:
        if (
            resolved_reasoning_effort
            and _provider_supports_reasoning_effort(resolved_base_url)
        ):
            resolved_reasoning = resolved_reasoning_effort

    max_input_tokens = _get_model_max_input_tokens(model_name)
    return ChatOpenAI(
        model=model_name,
        api_key=SecretStr(api_key),
        base_url=resolved_base_url,
        temperature=resolved_temperature,
        timeout=resolved_timeout,
        reasoning_effort=resolved_reasoning,
        extra_body=resolved_extra_body,
        # SDK-level exponential backoff (honors Retry-After) for 429/5xx; the
        # agent path adds ModelRetry middleware on top of this.
        max_retries=OPENAI_COMPATIBLE_MAX_RETRIES,
        profile={"max_input_tokens": max_input_tokens},
    )
