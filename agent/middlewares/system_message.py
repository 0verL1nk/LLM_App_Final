"""Utilities for maintaining a single provider-facing system message."""

from langchain_core.messages import SystemMessage


def _system_content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def append_system_instruction(
    system_message: SystemMessage | None,
    instruction: str,
) -> SystemMessage | None:
    """Append an instruction while preserving a single system-message envelope."""
    normalized = str(instruction or "").strip()
    if not normalized:
        return system_message
    if system_message is None:
        return SystemMessage(content=normalized)

    current = _system_content_text(system_message.content).strip()
    content = f"{current}\n\n{normalized}" if current else normalized
    return system_message.model_copy(update={"content": content})


__all__ = ["append_system_instruction"]
