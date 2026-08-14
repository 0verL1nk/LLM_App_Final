"""Safe message encoding for a resumed Leader continuation."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage


def build_continuation_tool_message(
    result: dict[str, Any], *, evidence_merge: dict[str, Any] | None = None
) -> ToolMessage:
    """Convert a validated child packet into the matching delegate-tool response."""
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    content = {
        "task_uid": str(result.get("task_uid") or ""),
        "role": str(result.get("role") or "unknown"),
        "status": str(result.get("status") or "failed"),
        "packet": packet,
        "error_message": str(result.get("error_message") or ""),
    }
    if evidence_merge is not None:
        content["evidence_merge"] = evidence_merge
    return ToolMessage(
        name="delegate_task",
        tool_call_id=str(result.get("tool_call_id") or ""),
        content=json.dumps(content, ensure_ascii=False),
    )


__all__ = ["build_continuation_tool_message"]
