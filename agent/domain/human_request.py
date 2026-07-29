"""Human-confirmation request contract and message extraction."""

import json
import re
from typing import Any, TypedDict


class HumanRequest(TypedDict):
    request_id: str
    question: str
    context: str
    urgency: str


_ANSWERED_REQUEST_ID = re.compile(
    r"\[Human confirmation response\].*?^Request ID:\s*(\S+)",
    re.DOTALL | re.MULTILINE,
)


def extract_human_requests(messages: list[Any]) -> list[HumanRequest]:
    """Extract deduplicated ``ask_human`` calls from an agent message sequence."""
    requests: list[HumanRequest] = []
    seen: set[tuple[str, str, str]] = set()

    def append_request(*, request_id: str, question: str, context: str, urgency: str) -> None:
        normalized_question = str(question or "").strip()
        if not normalized_question:
            return
        normalized_context = str(context or "").strip()
        normalized_urgency = str(urgency or "normal").strip().lower()
        if normalized_urgency not in {"low", "normal", "high"}:
            normalized_urgency = "normal"
        key = (normalized_question, normalized_context, normalized_urgency)
        if key in seen:
            return
        seen.add(key)
        requests.append(
            {
                "request_id": str(request_id or f"human-request-{len(requests) + 1}"),
                "question": normalized_question,
                "context": normalized_context,
                "urgency": normalized_urgency,
            }
        )

    for message in messages:
        tool_calls = _message_attr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict) or str(call.get("name") or "") != "ask_human":
                    continue
                args = call.get("args")
                if not isinstance(args, dict):
                    continue
                append_request(
                    request_id=str(call.get("id") or ""),
                    question=str(args.get("question") or ""),
                    context=str(args.get("context") or ""),
                    urgency=str(args.get("urgency") or "normal"),
                )

        role = str(
            _message_attr(message, "type", "") or _message_attr(message, "role", "") or ""
        ).lower()
        if role != "tool" or str(_message_attr(message, "name", "") or "") != "ask_human":
            continue
        try:
            payload = json.loads(str(_message_attr(message, "content", "") or ""))
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        append_request(
            request_id=str(_message_attr(message, "tool_call_id", "") or ""),
            question=str(payload.get("question") or ""),
            context=str(payload.get("context") or ""),
            urgency=str(payload.get("urgency") or "normal"),
        )
    return requests


def build_human_reply_prompt(request: HumanRequest, reply: str) -> str:
    """Build an explicit follow-up prompt for the same checkpoint thread."""
    return (
        "[Human confirmation response]\n"
        f"Request ID: {request['request_id']}\n"
        f"Question: {request['question']}\n"
        f"Context: {request['context'] or '(none)'}\n"
        f"Human response: {str(reply or '').strip()}\n"
        "Continue the original task using this response. Do not ask the same question again."
    )


def extract_answered_request_ids(messages: list[Any]) -> set[str]:
    """Find confirmation request IDs already answered in persisted user turns."""
    answered: set[str] = set()
    for message in messages:
        role = str(
            _message_attr(message, "role", "") or _message_attr(message, "type", "") or ""
        ).lower()
        if role not in {"user", "human"}:
            continue
        content = str(_message_attr(message, "content", "") or "")
        answered.update(match.strip() for match in _ANSWERED_REQUEST_ID.findall(content))
    return answered


def _message_attr(message: Any, name: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(name, default)
    return getattr(message, name, default)


__all__ = [
    "HumanRequest",
    "build_human_reply_prompt",
    "extract_answered_request_ids",
    "extract_human_requests",
]
