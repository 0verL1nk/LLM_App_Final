"""V2-only SSE streaming for Run events with afterSeq replay."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent.adapters.orm.run_repository import (
    get_run,
    list_run_events,
    list_run_items,
)

from .dependencies import current_user_id

router = APIRouter(tags=["runs"])

UserId = Annotated[str, Depends(current_user_id)]

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _v2_frames(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only versioned V2 events reach the wire; V1 rows stay storage-only."""
    return [event for event in events if int(event.get("version") or 1) >= 2]


@router.get("/runs/{run_uid}/events")
async def stream_agent_run_events(
    run_uid: str,
    user_uuid: UserId,
    afterSeq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream() -> AsyncIterator[str]:
        cursor = afterSeq
        while True:
            for event in _v2_frames(list_run_events(run_uid=run_uid, after_sequence=cursor)):
                cursor = max(cursor, int(event["sequence"]))
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            current = get_run(run_uid=run_uid, user_uuid=user_uuid)
            if current is None or str(current.get("status")) in _TERMINAL_RUN_STATUSES:
                break
            # Live runs: poll for new events until the Run terminates.
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Run-Events-Version": "2", "Cache-Control": "no-store"},
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
