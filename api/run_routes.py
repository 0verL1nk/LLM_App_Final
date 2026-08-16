"""V2-only SSE streaming for Run events with afterSeq replay."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from agent.adapters.orm.run_repository import (
    expire_stalled_runs,
    get_run,
    list_run_events,
    list_run_items,
)
from agent.settings import load_agent_settings

from .dependencies import current_user_id

router = APIRouter(tags=["runs"])

UserId = Annotated[str, Depends(current_user_id)]

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
_POLL_INTERVAL_SECONDS = 0.25
_HEARTBEAT_SECONDS = 15.0


def _v2_frames(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only versioned V2 events reach the wire; V1 rows stay storage-only."""
    return [event for event in events if int(event.get("version") or 1) >= 2]


@router.get("/runs/{run_uid}/events")
async def stream_agent_run_events(
    run_uid: str,
    user_uuid: UserId,
    afterSeq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    run = await run_in_threadpool(get_run, run_uid=run_uid, user_uuid=user_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream() -> AsyncIterator[str]:
        sequence = afterSeq
        heartbeat_at = asyncio.get_running_loop().time()
        max_idle_seconds = load_agent_settings().agent_llm_request_timeout + 30
        while True:
            events = _v2_frames(
                await run_in_threadpool(list_run_events, run_uid=run_uid, after_sequence=sequence)
            )
            for event in events:
                sequence = max(sequence, int(event["sequence"]))
                yield (
                    f"id: {event['eventId']}\n"
                    f"event: {event['eventType']}\n"
                    f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                )
            current = await run_in_threadpool(get_run, run_uid=run_uid, user_uuid=user_uuid)
            # Drain guard: the status flip and the terminal event append are two
            # separate writes; only close after terminal status is observed with
            # an empty poll so the client never misses run.completed/failed.
            if current is None or (
                str(current.get("status")) in _TERMINAL_RUN_STATUSES and not events
            ):
                break
            now = asyncio.get_running_loop().time()
            if now - heartbeat_at >= _HEARTBEAT_SECONDS:
                await run_in_threadpool(
                    expire_stalled_runs,
                    project_uid=str(current.get("project_uid") or run.get("project_uid") or ""),
                    session_uid=str(current.get("session_uid") or run.get("session_uid") or ""),
                    user_uuid=user_uuid,
                    max_idle_seconds=max_idle_seconds,
                )
                yield ": ping\n\n"
                heartbeat_at = now
            # Live runs: poll for new events until the Run terminates.
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Run-Events-Version": "2",
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_uid}/items")
def read_agent_run_items(
    run_uid: str,
    user_uuid: UserId,
    afterSeq: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return the owned V2 item snapshot and the replay cursor."""
    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    snapshot = list_run_items(run_uid=run_uid, after_sequence=afterSeq)
    return {"data": snapshot["items"], "lastSequence": snapshot["lastSequence"]}
