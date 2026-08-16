"""Owned durable task and research-artifact HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from agent.adapters.orm.research_artifact_repository import list_research_artifacts
from agent.adapters.orm.run_repository import get_run
from agent.adapters.orm.runtime_metrics_repository import get_runtime_metrics
from agent.adapters.orm.task_query_repository import (
    get_agent_task,
    list_agent_task_attempts,
    request_task_cancel,
    retry_agent_task,
)
from agent.application.task_delivery import dispatch_task

from .dependencies import current_user_id

runtime_task_router = APIRouter()
UserId = Annotated[str, Depends(current_user_id)]


@runtime_task_router.get("/runtime/metrics")
def read_runtime_metrics(user_uuid: UserId) -> dict[str, Any]:
    """Return operational metrics scoped to the authenticated owner's runtime facts."""
    return {"data": get_runtime_metrics(user_uuid=user_uuid)}


@runtime_task_router.get("/projects/{project_uid}/sessions/{session_uid}/research-artifacts")
def list_session_research_artifacts(
    project_uid: str,
    session_uid: str,
    user_uuid: UserId,
) -> dict[str, Any]:
    """Return evidence-backed artifacts scoped through their owning durable Runs."""
    return {
        "data": list_research_artifacts(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
        )
    }


@runtime_task_router.get("/tasks/{task_uid}")
def read_agent_task(task_uid: str, user_uuid: UserId) -> dict[str, Any]:
    """Read one owned durable task with its execution attempts."""
    task = _owned_task(task_uid, user_uuid)
    task["attempts"] = list_agent_task_attempts(task_uid=task_uid)
    return {"data": task}


@runtime_task_router.post("/tasks/{task_uid}/cancel")
def cancel_agent_task(task_uid: str, user_uuid: UserId) -> dict[str, Any]:
    """Request idempotent cancellation; a worker emits the final task outcome."""
    task = _owned_task(task_uid, user_uuid)
    changed = request_task_cancel(task_uid=task_uid)
    return {"data": {"task_uid": task["task_uid"], "cancel_requested": changed}}


@runtime_task_router.post("/tasks/{task_uid}/retry", status_code=202)
def retry_agent_task_route(task_uid: str, user_uuid: UserId) -> dict[str, Any]:
    """Queue a new task from an owned terminal unsuccessful task."""
    _owned_task(task_uid, user_uuid)
    try:
        task = retry_agent_task(task_uid=task_uid)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    dispatch_task(task_uid=str(task["task_uid"]))
    return {"data": task}


def _owned_task(task_uid: str, user_uuid: str) -> dict[str, Any]:
    task = get_agent_task(task_uid=task_uid)
    if task is None or get_run(run_uid=str(task["run_uid"]), user_uuid=user_uuid) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


__all__ = ["runtime_task_router"]
