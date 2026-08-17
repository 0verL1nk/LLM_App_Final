"""Projection of observable runtime facts into the V2 Run-item protocol."""

from __future__ import annotations

from typing import Any

_MAX_TEXT_LENGTH = 600
_MAX_LABEL_ARG_LENGTH = 72
_SENSITIVE_KEYS = {"api_key", "authorization", "password", "secret", "token"}
# Ordered by how descriptive each key typically is for a tool-row label.
_LABEL_ARG_KEYS = (
    "query",
    "question",
    "skill_name",
    "prompt",
    "task",
    "description",
    "url",
    "title",
    "search",
    "doc_name",
    "name",
    "text",
)


def project_runtime_item_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one public runtime fact to a typed V2 item lifecycle event.

    This intentionally has no V1 fallback.  Item identity comes from a concrete
    part ID or tool-call ID, never from role/description correlation.
    """
    performative = str(event.get("performative") or "")
    metadata = dict(event["metadata"]) if isinstance(event.get("metadata"), dict) else {}
    if performative == "answer_part_delta":
        part_id = str(metadata.get("part_id") or "text-0")
        item_type = "reasoning_summary" if part_id.startswith("reasoning-") else "assistant_message"
        return _item_event(
            item_uid=f"item_{item_type}_{part_id}",
            item_type=item_type,
            status="in_progress",
            event_type="item.delta",
            payload={"partId": part_id, "delta": _safe_text(event.get("content") or "")},
        )
    if performative == "answer_part_insert":
        part_id = str(metadata.get("part_id") or "").strip()
        part_type = str(metadata.get("part_type") or "")
        if not part_id or part_type not in {"reasoning", "a2ui"}:
            return None
        item_type = "reasoning_summary" if part_type == "reasoning" else "presentation"
        return _item_event(
            item_uid=f"item_{item_type}_{part_id}",
            item_type=item_type,
            status="in_progress",
            event_type="item.created",
            payload={"partId": part_id, "presentation": part_type} if part_type == "a2ui" else {"partId": part_id},
        )
    if performative == "presentation_failed":
        part_id = str(metadata.get("part_id") or "").strip()
        if not part_id:
            return None
        return _item_event(
            item_uid=f"item_presentation_{part_id}",
            item_type="presentation",
            status="failed",
            event_type="item.failed",
            payload={"partId": part_id, "message": _safe_text(metadata.get("message") or "可视化内容不可用")},
        )
    if performative not in {"tool_call", "tool_result"}:
        return None
    tool_name = str(metadata.get("tool_name") or event.get("receiver") or "unknown")
    action_id = str(metadata.get("tool_call_id") or "").strip()
    if not action_id:
        return None
    is_plan = tool_name == "update_plan"
    task_uid = str(metadata.get("task_uid") or "").strip() or None
    is_task = tool_name == "delegate_task" and task_uid is not None
    item_type = "agent_task" if is_task else "plan" if is_plan else "tool_call"
    payload = {
        "summary": _safe_text(metadata.get("summary") or event.get("content") or ""),
        "toolName": tool_name,
        "durationMs": _positive_number(metadata.get("duration_ms")),
    }
    arguments = metadata.get("arguments") if isinstance(metadata.get("arguments"), dict) else {}
    if is_task:
        payload.update({"agent": _safe_text(arguments.get("role") or "unknown"), "task": _safe_text(arguments.get("description") or payload["summary"])})
    if is_plan:
        payload["plan"] = _safe_value(
            {"goal": arguments.get("goal"), "steps": arguments.get("steps") or []}
        )
    else:
        # Row label and expandable detail: the label must stay a short
        # "tool + key argument" line; the raw result text is for the
        # expanded body, never the collapsed row title.
        payload["label"] = _tool_label(tool_name, arguments)
        if arguments:
            payload["arguments"] = _safe_value(arguments)
    terminal = performative == "tool_result"
    failed = str(metadata.get("status") or "").lower() in {"error", "failed"}
    if terminal:
        payload["result"] = payload["summary"]
    return _item_event(
        item_uid=f"item_{item_type}_{task_uid or action_id}",
        item_type=item_type,
        task_uid=task_uid,
        status="failed" if terminal and failed else "completed" if terminal else "in_progress",
        event_type="item.failed" if terminal and failed else "item.completed" if terminal else "item.created",
        payload=payload,
    )


def project_presentation_item_event(
    *,
    part_id: str,
    envelope: dict[str, Any],
    surface: dict[str, Any],
) -> dict[str, Any]:
    """Create one V2 presentation delta from a validated A2UI envelope."""
    return _item_event(
        item_uid=f"item_presentation_{part_id or surface.get('surfaceId', 'default')}",
        item_type="presentation",
        status="completed",
        event_type="item.delta",
        payload={"partId": part_id, "envelope": envelope, "surface": _safe_value(surface)},
    )


def _item_event(
    *,
    item_uid: str,
    item_type: str,
    status: str,
    event_type: str,
    payload: dict[str, Any],
    task_uid: str | None = None,
) -> dict[str, Any]:
    return {"item_uid": item_uid, "item_type": item_type, "task_uid": task_uid, "status": status, "event_type": event_type, "payload": payload}


def _safe_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text[:_MAX_TEXT_LENGTH]


def _tool_label(tool_name: str, arguments: dict[str, Any]) -> str:
    """One short row label: tool name plus its most descriptive argument."""
    candidate_keys = [key for key in _LABEL_ARG_KEYS if key in arguments]
    candidate_keys.extend(
        key for key in arguments if key not in candidate_keys and str(key).lower() not in _SENSITIVE_KEYS
    )
    for key in candidate_keys:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            snippet = _safe_text(value)[:_MAX_LABEL_ARG_LENGTH]
            return f'{tool_name} "{snippet}"'
    return tool_name


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items() if str(key).lower() not in _SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _positive_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


__all__ = ["project_presentation_item_event", "project_runtime_item_event"]
