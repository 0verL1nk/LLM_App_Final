"""Durable execution entry points for research Runs and their item projections."""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.orm.run_repository import (
    append_run_item_event,
    append_run_lifecycle_event,
    claim_run_execution,
    get_run,
    get_run_item,
    update_run_status,
)
from ..domain.run_item import RunItemProtocolError
from .contracts import EmptyModelOutputError
from .research_workspace import research_workspace_service
from .run_timeline import (
    presentation_item_uid,
    project_presentation_completion_event,
    project_presentation_item_event,
    project_runtime_item_event,
)

logger = logging.getLogger(__name__)


def record_item_event(**kwargs: Any) -> None:
    """Persist one projected item event without letting a mismatch kill the turn.

    The repository boundary still rejects unknown types, statuses and lifecycle
    violations before writing; a projector regression must not abort a paid
    model call mid-stream.
    """
    try:
        append_run_item_event(**kwargs)
    except RunItemProtocolError as exc:
        logger.warning("Rejected run item event before persistence: %s", exc)


def execute_research_run(
    *,
    run_uid: str,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    prompt: str,
    leader_task_uid: str | None = None,
    steering_initial_delivery: bool = False,
    resolved_mode: str = "agent_teams",
) -> dict[str, Any]:
    """Queue worker entry point that persists every public runtime event."""
    if not claim_run_execution(run_uid=run_uid):
        return {"waiting_children": False}
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.started", payload={"status": "running"})

    def record_event(event: dict[str, Any]) -> None:
        if str(event.get("performative") or "") == "a2ui_surface_ready":
            metadata: dict[str, Any] = (
                dict(event["metadata"]) if isinstance(event.get("metadata"), dict) else {}
            )
            surface = metadata.get("surface") if isinstance(metadata.get("surface"), dict) else None
            part_id = str(metadata.get("part_id") or "")
            if surface is not None:
                _append_surface_events(run_uid=run_uid, surface=surface, part_id=part_id)
            return
        item_event = project_runtime_item_event(event)
        if item_event is not None:
            record_item_event(
                run_uid=run_uid,
                item_uid=str(item_event["item_uid"]),
                item_type=str(item_event["item_type"]),
                status=str(item_event["status"]),
                event_type=str(item_event["event_type"]),
                payload=dict(item_event["payload"]),
                task_uid=item_event.get("task_uid"),
            )

    try:
        result = research_workspace_service.execute_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt=prompt,
            on_event=record_event,
            user_message_persisted=True,
            run_uid=run_uid,
            leader_task_uid=leader_task_uid,
            steering_initial_delivery=steering_initial_delivery,
            resolved_mode=resolved_mode,
        )
    except Exception as exc:
        update_run_status(run_uid=run_uid, status="failed", error_message=str(exc))
        public_message = (
            "模型未返回有效内容，自动重试后仍然失败，请重新发送"
            if isinstance(exc, EmptyModelOutputError)
            else "模型执行失败，请稍后重试"
        )
        record_item_event(
            run_uid=run_uid,
            item_uid=f"item_failure_{run_uid}",
            item_type="failure",
            status="failed",
            event_type="item.failed",
            payload={"message": public_message},
        )
        append_run_lifecycle_event(
            run_uid=run_uid,
            event_type="run.failed",
            payload={"message": public_message},
        )
        raise
    a2ui_surfaces = result.get("a2ui_surfaces") if isinstance(result, dict) else None
    if not isinstance(a2ui_surfaces, list) and isinstance(result, dict):
        legacy_surface = result.get("a2ui_surface")
        a2ui_surfaces = [legacy_surface] if isinstance(legacy_surface, dict) else []
    if isinstance(a2ui_surfaces, list):
        for surface in a2ui_surfaces:
            if isinstance(surface, dict):
                _append_surface_events(
                    run_uid=run_uid,
                    surface=surface,
                    part_id=str(surface.get("partId") or ""),
                    data_only=True,
                )
    _complete_response_part_items(run_uid=run_uid, result=result)
    from ..adapters.orm.task_parent_repository import has_nonterminal_child_tasks

    waiting_children = bool(
        leader_task_uid
        and has_nonterminal_child_tasks(parent_task_uid=leader_task_uid)
    )
    update_run_status(
        run_uid=run_uid,
        status="waiting_children" if waiting_children else "completed",
    )
    append_run_lifecycle_event(
        run_uid=run_uid,
        event_type="run.waiting_children" if waiting_children else "run.completed",
        payload={"result": result} if not waiting_children else {"status": "waiting_children"},
    )
    followup = research_workspace_service.prepare_steering_followup_run(
        source_run_uid=run_uid,
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
    )
    if followup is not None:
        from .task_delivery import dispatch_task

        dispatch_task(task_uid=str(followup["leader_task_uid"]))
    return {"waiting_children": waiting_children}


def execute_research_continuation(
    *,
    continuation_task_uid: str,
    run_uid: str,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    parent_task_uid: str,
    tool_results: list[dict[str, Any]],
    evidence_merge: dict[str, Any] | None = None,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Resume a waiting Run after all child packets are durably available."""
    update_run_status(run_uid=run_uid, status="running")
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.resumed", payload={"task_uid": continuation_task_uid})

    def record_event(event: dict[str, Any]) -> None:
        item_event = project_runtime_item_event(event)
        if item_event is None:
            return
        record_item_event(
            run_uid=run_uid,
            item_uid=str(item_event["item_uid"]),
            item_type=str(item_event["item_type"]),
            status=str(item_event["status"]),
            event_type=str(item_event["event_type"]),
            payload=dict(item_event["payload"]),
            task_uid=item_event.get("task_uid"),
        )

    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    resolved_mode = str((run or {}).get("resolved_mode") or "react")
    try:
        result = research_workspace_service.execute_continuation_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            parent_task_uid=parent_task_uid,
            tool_results=tool_results,
            evidence_merge=evidence_merge,
            on_event=record_event,
            run_uid=run_uid,
            resolved_mode=resolved_mode,
            part_scope=_continuation_part_scope(continuation_task_uid, db_name=db_name),
        )
    except Exception as exc:
        update_run_status(run_uid=run_uid, status="failed", error_message=str(exc))
        record_item_event(
            run_uid=run_uid,
            item_uid=f"item_failure_{run_uid}",
            item_type="failure",
            status="failed",
            event_type="item.failed",
            payload={"message": "子研究结果整合失败，请重试。"},
        )
        append_run_lifecycle_event(
            run_uid=run_uid,
            event_type="run.failed",
            payload={"message": "子研究结果整合失败，请重试。"},
        )
        raise
    _complete_response_part_items(run_uid=run_uid, result=result)
    update_run_status(run_uid=run_uid, status="completed")
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": result})
    return {"summary": str(result.get("answer") or "研究结果已整合"), "parent_task_uid": parent_task_uid}


def _continuation_part_scope(continuation_task_uid: str, *, db_name: str = "./database.sqlite") -> str:
    """Give one resumed turn item ids that never collide with earlier turns."""
    try:
        from ..adapters.orm.task_query_repository import get_agent_task

        task = get_agent_task(task_uid=continuation_task_uid, db_name=db_name)
        epoch = int((task or {}).get("continuation_epoch") or 0)
    except (LookupError, TypeError, ValueError):
        epoch = 0
    return f"e{epoch}" if epoch > 0 else f"c{continuation_task_uid[-8:]}"


def _append_surface_events(
    *,
    run_uid: str,
    surface: dict[str, Any],
    part_id: str,
    data_only: bool = False,
) -> None:
    """Persist catalog messages for one anchored UI surface in stream order.

    Already-persisted envelopes are skipped so replayed or updated surfaces never
    duplicate content; the final call closes the item with one terminal event.
    """
    messages = surface.get("messages")
    if not isinstance(messages, list):
        return
    metadata: dict[str, Any] = {
        "catalogId": surface.get("catalogId"),
        "surfaceId": surface.get("surfaceId"),
        "title": surface.get("title"),
    }
    if part_id:
        metadata["partId"] = part_id
    item_uid = presentation_item_uid(part_id, surface)
    persisted = get_run_item(run_uid=run_uid, item_uid=item_uid)
    persisted_status = str((persisted or {}).get("status") or "")
    envelopes = (persisted or {}).get("payload", {}).get("envelopes") or []
    pending = [item for item in messages if isinstance(item, dict)][len(envelopes) :]
    for envelope in pending:
        item_event = project_presentation_item_event(
            part_id=part_id,
            envelope=envelope,
            surface=metadata,
        )
        record_item_event(
            run_uid=run_uid,
            item_uid=str(item_event["item_uid"]),
            item_type=str(item_event["item_type"]),
            status=str(item_event["status"]),
            event_type=str(item_event["event_type"]),
            payload=dict(item_event["payload"]),
        )
    # A surface that never streamed is materialized by this call's own deltas.
    if data_only and (persisted_status == "in_progress" or (persisted is None and pending)):
        completion = project_presentation_completion_event(part_id=part_id, surface=metadata)
        record_item_event(
            run_uid=run_uid,
            item_uid=str(completion["item_uid"]),
            item_type=str(completion["item_type"]),
            status=str(completion["status"]),
            event_type=str(completion["event_type"]),
            payload=dict(completion["payload"]),
        )


def _complete_response_part_items(*, run_uid: str, result: dict[str, Any]) -> None:
    """Mark persisted text/reasoning parts terminal once the Run completed safely."""
    response_parts = result.get("response_parts")
    if not isinstance(response_parts, list):
        return
    for part in response_parts:
        if not isinstance(part, dict):
            continue
        part_id = str(part.get("id") or "").strip()
        part_type = str(part.get("type") or "")
        text = part.get("text")
        if not part_id or not isinstance(text, str) or part_type not in {"markdown", "reasoning"}:
            continue
        item_type = "assistant_message" if part_type == "markdown" else "reasoning_summary"
        record_item_event(
            run_uid=run_uid,
            item_uid=f"item_{item_type}_{part_id}",
            item_type=item_type,
            status="completed",
            event_type="item.completed",
            payload={"partId": part_id, "text": text},
        )


__all__ = ["execute_research_continuation", "execute_research_run", "record_item_event"]
