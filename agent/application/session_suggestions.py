"""Per-session follow-up suggestions generated from the user's model."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from ..adapters.user_settings import (
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
)
from ..llm_provider import build_openai_compatible_chat_model, invoke_structured_model

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 4
RECENT_MESSAGE_LIMIT = 8
MESSAGE_SNIPPET_CHARS = 400


class FollowUpSuggestions(BaseModel):
    items: list[str] = Field(default_factory=list)


_SYSTEM_PROMPT = """You propose follow-up prompts for a research assistant.
Use the recent conversation when present, otherwise the project's library
document list. Return up to 4 concrete next-step prompts in the user's
language (default Chinese).

Rules:
- every item is a ready-to-send user prompt, short and specific;
- ground items in the given context; never invent document names or claims;
- no duplicates and no filler such as "继续" or "还有吗";
- return JSON exactly like {"items": ["…", "…"]}."""


def generate_session_suggestions(
    *,
    user_uuid: str,
    project_uid: str,
    session_uid: str,
    messages: list[dict[str, Any]],
    document_names: list[str],
) -> list[str]:
    """Suggest follow-up prompts; returns [] whenever no model is configured."""
    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        return []
    try:
        model = build_openai_compatible_chat_model(
            api_key=api_key,
            model_name=model_name,
            base_url=read_base_url_for_user(uuid=user_uuid),
            temperature=0.4,
        )
        recent = [
            {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")[:MESSAGE_SNIPPET_CHARS]}
            for item in messages[-RECENT_MESSAGE_LIMIT:]
        ]
        payload = {
            "project_uid": project_uid,
            "session_uid": session_uid,
            "recent_messages": recent,
            "library_documents": document_names,
        }
        result = invoke_structured_model(
            model,
            FollowUpSuggestions,
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        return [item.strip() for item in result.items if item.strip()][:MAX_SUGGESTIONS]
    except Exception:
        logger.exception("Session suggestions failed: session_uid=%s", session_uid)
        return []


__all__ = ["FollowUpSuggestions", "generate_session_suggestions"]
