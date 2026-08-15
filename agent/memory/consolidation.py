"""Model-driven background consolidation for project-scoped long-term memory."""

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from ..llm_provider import invoke_structured_model
from .repository import (
    apply_memory_consolidation,
    claim_memory_event,
    list_project_memory_items,
    mark_memory_event,
)

logger = logging.getLogger(__name__)


class MemoryOperation(BaseModel):
    action: Literal["create", "update", "delete"]
    memory_uid: str = Field(default="", description="Required for update/delete")
    memory_type: Literal["semantic", "episodic", "procedural"] = "semantic"
    title: str = ""
    content: str = ""
    reason: str = ""


class MemoryConsolidation(BaseModel):
    operations: list[MemoryOperation] = Field(default_factory=list)


_SYSTEM_PROMPT = """You are the long-term memory consolidation agent for a research assistant.
Review one completed conversation turn together with existing project memories.
Return only structured operations.

Store only information that will improve future work across sessions:
- stable user preferences or explicit standing instructions;
- durable project facts explicitly supplied by the user or grounded in the completed work;
- reusable successful/failed workflow experience when it changes future execution.

Do not store greetings, transient requests, generic model prose, unsupported claims, raw chain-of-thought,
secrets, credentials, or information already represented by an existing memory.
Update an existing memory when new information refines or contradicts it. Delete a memory only when the
new turn explicitly invalidates it. Keep every memory atomic, concise, self-contained, and provenance-aware.
Procedural memories are preferences/instructions, semantic memories are durable facts, and episodic memories
are reusable experiences. If nothing deserves long-term retention, return an empty operations list."""


def _build_model_for_user(user_uuid: str):
    """Resolve user configuration lazily to avoid adapter/utils import cycles."""
    from agent.adapters.user_settings import (
        read_api_key_for_user,
        read_base_url_for_user,
        read_model_name_for_user,
    )
    from agent.llm_provider import build_openai_compatible_chat_model

    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        raise RuntimeError("Memory consolidation requires configured API key and model")
    return build_openai_compatible_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=read_base_url_for_user(uuid=user_uuid),
        temperature=0.0,
    )


def process_memory_event(event_uid: str, db_name: str = "./database.sqlite") -> None:
    """Process one durable event; safe to invoke from RQ or the local thread queue."""
    event = claim_memory_event(event_uid=event_uid, db_name=db_name)
    if event is None:
        return
    try:
        llm = _build_model_for_user(event["uuid"])
        existing = list_project_memory_items(
            uuid=event["uuid"],
            project_uid=event["project_uid"],
            limit=200,
            db_name=db_name,
        )
        payload = {
            "existing_memories": [
                {
                    "memory_uid": item["memory_uid"],
                    "memory_type": item["memory_type"],
                    "title": item["title"],
                    "content": item["content"],
                }
                for item in existing
            ],
            "completed_turn": {
                "user": event["prompt"],
                "assistant": event["answer"],
            },
        }
        consolidation = invoke_structured_model(
            llm,
            MemoryConsolidation,
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        apply_memory_consolidation(
            event=event,
            operations=[operation.model_dump() for operation in consolidation.operations],
            db_name=db_name,
        )
        mark_memory_event(
            event_uid=event_uid,
            status="completed",
            clear_payload=True,
            db_name=db_name,
        )
    except Exception as exc:
        mark_memory_event(
            event_uid=event_uid,
            status="failed",
            error_message=str(exc),
            db_name=db_name,
        )
        logger.exception("Memory consolidation failed: event_uid=%s", event_uid)


__all__ = ["MemoryConsolidation", "MemoryOperation", "process_memory_event"]
