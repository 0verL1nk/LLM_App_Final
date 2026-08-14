"""Owned management endpoints for user-visible L3/L4 memory only."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException

from agent.adapters.orm.memory_repository import (
    delete_memory_item,
    list_memory_items,
    update_memory_item,
    upsert_memory_item,
)
from agent.application.workspace import require_project

from .dependencies import current_user_id
from .schemas import MemoryItemWrite

context_memory_router = APIRouter()
UserId = Annotated[str, Depends(current_user_id)]
MemoryLevel = Literal["L3", "L4"]


@context_memory_router.get("/projects/{project_uid}/memory/{level}")
def list_context_memory(project_uid: str, level: MemoryLevel, user_uuid: UserId) -> dict:
    """List project memory or user preference entries without source prompts."""
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    return {"data": list_memory_items(uuid=user_uuid, project_uid=project_uid, level=level)}


@context_memory_router.post("/projects/{project_uid}/memory/{level}")
def create_context_memory(
    project_uid: str, level: MemoryLevel, payload: MemoryItemWrite, user_uuid: UserId
) -> dict:
    """Create an explicit L3 project memory or L4 stable preference."""
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    uid = upsert_memory_item(
        uuid=user_uuid, project_uid=project_uid, level=level,
        memory_type=payload.memory_type, title=payload.title, content=payload.content,
    )
    return {"data": {"memory_uid": uid}}


@context_memory_router.patch("/projects/{project_uid}/memory/{level}/{memory_uid}")
def edit_context_memory(
    project_uid: str, level: MemoryLevel, memory_uid: str, payload: MemoryItemWrite, user_uuid: UserId
) -> dict:
    """Edit only the caller-owned L3/L4 item; server-created L1/L2 stay immutable."""
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    if not update_memory_item(
        memory_uid=memory_uid, uuid=user_uuid, project_uid=project_uid, level=level,
        title=payload.title, content=payload.content,
    ):
        raise HTTPException(status_code=404, detail="Memory item not found")
    return {"data": {"memory_uid": memory_uid}}


@context_memory_router.delete("/projects/{project_uid}/memory/{level}/{memory_uid}", status_code=204)
def remove_context_memory(project_uid: str, level: MemoryLevel, memory_uid: str, user_uuid: UserId) -> None:
    """Delete one caller-owned managed entry."""
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    if not delete_memory_item(memory_uid=memory_uid, uuid=user_uuid, project_uid=project_uid, level=level):
        raise HTTPException(status_code=404, detail="Memory item not found")
