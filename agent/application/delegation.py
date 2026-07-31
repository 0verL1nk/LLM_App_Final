import json
import re
from typing import Any, TypedDict

_EVIDENCE_REF = re.compile(r"<evidence>([^<]+)</evidence>", re.IGNORECASE)
_URL_REF = re.compile(r"https?://[^\s<>)\]]+")


class DelegatedTask(TypedDict):
    task_id: str
    subagent_type: str
    description: str
    status: str
    output: str
    round: int
    parallel: bool
    parallel_requested: bool
    evidence_refs: list[str]
    started_at_ms: float | None
    completed_at_ms: float | None
    duration_ms: float | None


class DelegationExecution(TypedDict):
    enabled: bool
    rounds: int
    member_count: int
    roles: list[str]
    tasks: list[DelegatedTask]


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    raw = message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "").strip().lower()
    return str(getattr(message, "type", getattr(message, "role", "")) or "").strip().lower()


def _tool_result(message: Any) -> tuple[str, str, str] | None:
    if _message_role(message) != "tool":
        return None
    if isinstance(message, dict):
        tool_call_id = str(message.get("tool_call_id") or "").strip()
        content = str(message.get("content") or "")
        status = str(message.get("status") or "").strip().lower()
    else:
        tool_call_id = str(getattr(message, "tool_call_id", "") or "").strip()
        content = str(getattr(message, "content", "") or "")
        status = str(getattr(message, "status", "") or "").strip().lower()
    if not tool_call_id:
        return None
    failed = status == "error"
    return tool_call_id, content, "failed" if failed else "completed"


def build_delegation_execution(
    messages: list[Any], lifecycle_events: list[dict[str, Any]] | None = None
) -> DelegationExecution:
    """Derive observable delegation state from completed ``task`` tool calls."""
    results = {
        tool_call_id: (content, status)
        for message in messages
        if (result := _tool_result(message)) is not None
        for tool_call_id, content, status in [result]
    }
    tasks: list[DelegatedTask] = []
    round_number = 0
    for message in messages:
        calls = [call for call in _tool_calls(message) if str(call.get("name") or "") == "task"]
        if not calls:
            continue
        round_number += 1
        is_parallel = len(calls) > 1
        for index, call in enumerate(calls, start=1):
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            task_id = str(call.get("id") or f"delegation-{round_number}-{index}").strip()
            output, status = results.get(task_id, ("", "incomplete"))
            tasks.append(
                {
                    "task_id": task_id,
                    "subagent_type": str(args.get("subagent_type") or "unknown").strip(),
                    "description": str(args.get("description") or "").strip(),
                    "status": status,
                    "output": output,
                    "round": round_number,
                    "parallel": False,
                    "parallel_requested": is_parallel,
                    "evidence_refs": _extract_evidence_refs(output),
                    "started_at_ms": None,
                    "completed_at_ms": None,
                    "duration_ms": None,
                }
            )
    _attach_lifecycle_timings(tasks, lifecycle_events or [])
    for task in tasks:
        start = task["started_at_ms"]
        end = task["completed_at_ms"]
        if start is None or end is None:
            continue
        task["parallel"] = any(
            other is not task
            and other["started_at_ms"] is not None
            and other["completed_at_ms"] is not None
            and max(start, other["started_at_ms"]) < min(end, other["completed_at_ms"])
            for other in tasks
        )
    roles = sorted({task["subagent_type"] for task in tasks if task["subagent_type"] != "unknown"})
    return {
        "enabled": bool(tasks),
        "rounds": round_number,
        "member_count": len(tasks),
        "roles": roles,
        "tasks": tasks,
    }


def _extract_evidence_refs(output: str) -> list[str]:
    refs = [item.strip() for item in _EVIDENCE_REF.findall(output) if item.strip()]
    refs.extend(item.rstrip(".,;") for item in _URL_REF.findall(output))
    return list(dict.fromkeys(refs))


def _attach_lifecycle_timings(
    tasks: list[DelegatedTask], events: list[dict[str, Any]]
) -> None:
    timings: dict[tuple[str, str], list[dict[str, float]]] = {}
    for event in events:
        if str(event.get("performative") or "") != "subagent_complete":
            continue
        try:
            payload = json.loads(str(event.get("content") or ""))
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        key = (str(payload.get("role") or ""), str(payload.get("description") or ""))
        timings.setdefault(key, []).append(payload)
    for task in tasks:
        matches = timings.get((task["subagent_type"], task["description"]), [])
        if not matches:
            continue
        timing = matches.pop(0)
        task["started_at_ms"] = _optional_float(timing.get("started_at_ms"))
        task["completed_at_ms"] = _optional_float(timing.get("completed_at_ms"))
        task["duration_ms"] = _optional_float(timing.get("duration_ms"))


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


__all__ = ["DelegatedTask", "DelegationExecution", "build_delegation_execution"]
