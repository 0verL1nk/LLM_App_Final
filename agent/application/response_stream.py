"""Classify provider text into typed, user-renderable response parts."""

from __future__ import annotations

from collections.abc import Callable

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


class ResponseStreamPartRouter:
    """Route provider token deltas into Markdown and reasoning parts.

    Some OpenAI-compatible providers serialize reasoning as ``<think>`` tags in
    ordinary content. This adapter keeps that provider protocol out of Markdown
    while preserving the reasoning as a distinct, streamable message part.
    """

    def __init__(
        self,
        *,
        on_text: Callable[[str], None],
        on_reasoning: Callable[[str], None],
    ) -> None:
        self._on_text = on_text
        self._on_reasoning = on_reasoning
        self._buffer = ""
        self._inside_reasoning = False

    def feed(self, token: str) -> None:
        """Consume one possibly partial provider delta."""
        if not token:
            return
        self._buffer += token
        while self._buffer:
            if self._inside_reasoning:
                close_index = self._buffer.lower().find(_THINK_CLOSE)
                if close_index < 0:
                    self._emit_reasoning_except_possible_close()
                    return
                self._on_reasoning(self._buffer[:close_index])
                self._buffer = self._buffer[close_index + len(_THINK_CLOSE) :]
                self._inside_reasoning = False
                continue

            open_index = self._buffer.lower().find(_THINK_OPEN)
            if open_index < 0:
                self._emit_text_except_possible_open()
                return
            self._on_text(self._buffer[:open_index])
            self._buffer = self._buffer[open_index + len(_THINK_OPEN) :]
            self._inside_reasoning = True

    def finish(self) -> None:
        """Flush the final typed part after provider streaming completes."""
        if self._inside_reasoning:
            if self._buffer:
                self._on_reasoning(self._buffer)
        elif self._buffer:
            self._on_text(self._buffer)
        self._buffer = ""
        self._inside_reasoning = False

    def _emit_text_except_possible_open(self) -> None:
        trailing = _possible_tag_prefix_length(self._buffer, _THINK_OPEN)
        safe_text = self._buffer[:-trailing] if trailing else self._buffer
        if safe_text:
            self._on_text(safe_text)
        self._buffer = self._buffer[-trailing:] if trailing else ""

    def _emit_reasoning_except_possible_close(self) -> None:
        trailing = _possible_tag_prefix_length(self._buffer, _THINK_CLOSE)
        safe_text = self._buffer[:-trailing] if trailing else self._buffer
        if safe_text:
            self._on_reasoning(safe_text)
        self._buffer = self._buffer[-trailing:] if trailing else ""


def _possible_tag_prefix_length(value: str, tag: str) -> int:
    """Return a trailing partial protocol tag length that needs the next token."""
    lowered = value.lower()
    for length in range(min(len(lowered), len(tag) - 1), 0, -1):
        if tag.startswith(lowered[-length:]):
            return length
    return 0


__all__ = ["ResponseStreamPartRouter"]
