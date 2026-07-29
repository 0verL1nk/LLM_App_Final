"""Project internal agent events into a safe, public execution timeline."""

from __future__ import annotations

from typing import Any


_MAX_TEXT_LENGTH = 600
_SENSITIVE_KEYS = {"api_key", "authorization", "password", "secret", "token"}


def project_runtime_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return one user-visible, replayable event from a runtime trace event.

    This deliberately represents observable actions, never provider reasoning or
    private prompts. The persisted result is the contract consumed by the web UI.
    """
    performative = str(event.get("performative") or "")
    if performative == "answer_delta":
        return "answer.delta", {"text": _safe_text(event.get("content") or "")}
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    tool_name = str(metadata.get("tool_name") or event.get("receiver") or "unknown")
    payload = {
        "actionId": str(metadata.get("tool_call_id") or ""),
        "toolName": tool_name,
        "arguments": _safe_value(metadata.get("arguments") or {}),
        "summary": _safe_text(metadata.get("summary") or event.get("content") or ""),
        "durationMs": _positive_number(metadata.get("duration_ms")),
        "status": str(metadata.get("status") or ""),
    }

    if performative == "tool_call":
        if tool_name == "task":
            return "agent.spawned", _delegation_payload(payload)
        if tool_name in {"write_todos", "write_plan"}:
            return "plan.updated", _plan_payload(payload)
        return "tool.execution.started", payload
    if performative == "tool_result":
        if tool_name == "task":
            return "agent.completed", _delegation_payload(payload)
        if tool_name in {"write_todos", "write_plan"}:
            return "plan.updated", _plan_payload(payload)
        return "tool.execution.completed", payload
    if performative == "delegate_task":
        return "agent.spawned", _delegation_payload(payload)
    if performative == "delegate_result":
        return "agent.completed", _delegation_payload(payload)
    return "step.progress", {"summary": _safe_text(event.get("content") or "")}


def _delegation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
    return {
        "actionId": payload["actionId"],
        "agent": str(arguments.get("subagent_type") or "unknown"),
        "task": _safe_text(arguments.get("description") or payload["summary"]),
        "status": payload["status"] or "running",
        "durationMs": payload["durationMs"],
    }


def _plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
    todos = arguments.get("todos") if isinstance(arguments.get("todos"), list) else []
    return {
        "actionId": payload["actionId"],
        "todos": _safe_value(todos),
        "status": payload["status"] or "updated",
        "summary": payload["summary"],
    }


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:50]]
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in _SENSITIVE_KEYS else _safe_value(item)
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(value)


def _safe_text(value: Any) -> str:
    return str(value).replace("\x00", "")[:_MAX_TEXT_LENGTH]


def _positive_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


__all__ = ["project_runtime_event"]
