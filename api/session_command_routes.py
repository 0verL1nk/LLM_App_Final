"""Slash command endpoints: skill catalog listing and session command execution."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from agent.application.session_commands import (
    SessionCommandConflict,
    SessionCommandError,
    execute_session_command,
    list_skill_catalog,
)

from .dependencies import current_user_id
from .schemas import SessionCommandCreate

session_command_router = APIRouter()
UserId = Annotated[str, Depends(current_user_id)]
logger = logging.getLogger(__name__)


@session_command_router.get("/skills")
def read_skills(_user_uuid: UserId) -> dict[str, Any]:
    """List the merged user+bundled skill registry for slash command hints."""
    return {"data": list_skill_catalog()}


@session_command_router.post("/projects/{project_uid}/sessions/{session_uid}/commands")
async def run_session_command(
    project_uid: str,
    session_uid: str,
    payload: SessionCommandCreate,
    user_uuid: UserId,
) -> dict[str, Any]:
    """Execute one slash command without an agent run and persist its transcript."""
    try:
        result = await run_in_threadpool(
            execute_session_command,
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            command=payload.command,
            args=payload.args,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "Not found") from exc
    except SessionCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SessionCommandConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Session command failed: user=%s project=%s session=%s command=%s",
            user_uuid,
            project_uid,
            session_uid,
            payload.command,
        )
        raise HTTPException(status_code=502, detail="Model execution failed") from exc
    return {"data": result}
