"""Model-driven asynchronous naming for research sessions."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from ..adapters.sqlite.project_repository import list_project_sessions, update_project_session
from ..adapters.user_settings import read_api_key_for_user, read_base_url_for_user, read_model_name_for_user
from ..llm_provider import build_openai_compatible_chat_model

logger = logging.getLogger(__name__)

_UNTITLED_NAMES = {"默认会话", "新探索", "新会话", "未命名会话"}


class SessionTitle(BaseModel):
    """A concise, user-facing title generated from one completed turn."""

    title: str = Field(min_length=1, max_length=60)


_SYSTEM_PROMPT = """Generate one concise, user-facing title for this research conversation.
Use the user's language. Capture the specific topic or decision, not generic labels such as
'research', 'new conversation', or 'analysis'. Return only the structured title."""


def enqueue_session_title_generation(*, user_uuid: str, project_uid: str, session_uid: str, prompt: str, answer: str) -> None:
    """Queue title generation without delaying the completed research response."""
    from utils.task_queue import enqueue_background_task

    enqueue_background_task(
        generate_session_title,
        user_uuid=user_uuid,
        project_uid=project_uid,
        session_uid=session_uid,
        prompt=prompt,
        answer=answer,
    )


def generate_session_title(*, user_uuid: str, project_uid: str, session_uid: str, prompt: str, answer: str, db_name: str = "./database.sqlite") -> None:
    """Name an untouched session once its first useful answer is available."""
    session = next(
        (item for item in list_project_sessions(project_uid=project_uid, uuid=user_uuid, db_name=db_name) if item["session_uid"] == session_uid),
        None,
    )
    if session is None or str(session.get("session_name") or "") not in _UNTITLED_NAMES:
        return
    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        return
    try:
        model = build_openai_compatible_chat_model(
            api_key=api_key,
            model_name=model_name,
            base_url=read_base_url_for_user(uuid=user_uuid),
            temperature=0.0,
        )
        result = model.with_structured_output(SessionTitle).invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"用户问题：{prompt}\n\n助手回答：{answer}"},
        ])
        title = result.title if isinstance(result, SessionTitle) else SessionTitle.model_validate(result).title
        normalized_title = title.strip()
        if normalized_title:
            update_project_session(session_uid=session_uid, project_uid=project_uid, uuid=user_uuid, session_name=normalized_title, db_name=db_name)
    except Exception:
        logger.exception("Session title generation failed: session_uid=%s", session_uid)


__all__ = ["enqueue_session_title_generation", "generate_session_title"]
