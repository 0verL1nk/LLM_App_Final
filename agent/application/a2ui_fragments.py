"""Bounded parser for private inline UI fragments in a model token stream."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .a2ui_mindmap import MAX_CHILDREN, MAX_LABEL_LENGTH

_OPEN_UI = re.compile(r'(?m)^[ \t]*<ui\s+type="(?P<type>[a-z-]+)"\s*>')
_CLOSE_UI = "</ui>"
_MAX_FRAGMENT_BYTES = 32_000


class ResearchMapNodeDecision(BaseModel):
    """Strict, renderer-independent DTO for one parsed map node."""

    model_config = ConfigDict(extra="forbid", strict=True)

    label: str = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    children: list["ResearchMapNodeDecision"] = Field(default_factory=list, max_length=MAX_CHILDREN)
    citation_ids: list[str] = Field(default_factory=list, max_length=8)


ResearchMapNodeDecision.model_rebuild()


class ResearchMapDecision(BaseModel):
    """Strict decision before server compilation to an A2UI envelope."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["research_map"] = "research_map"
    title: str = Field(min_length=1, max_length=80)
    root: ResearchMapNodeDecision


@dataclass(frozen=True)
class PresentationDecision:
    """A validated product-level UI intent extracted from the stream.

    ``raw_xml`` keeps the fragment exactly as the model authored it; storage
    persists the content verbatim and the frontend owns rendering.
    """

    type: str
    payload: dict[str, Any]
    raw_xml: str = ""


class A2UIFragmentStreamParser:
    """Split Markdown tokens from complete, private XML UI fragments."""

    def __init__(
        self,
        *,
        on_text: Callable[[str], None],
        on_fragment_start: Callable[[str], None] | None = None,
        on_fragment: Callable[[PresentationDecision], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._on_text = on_text
        self._on_fragment_start = on_fragment_start
        self._on_fragment = on_fragment
        self._on_error = on_error
        self._text_buffer = ""
        self._fragment_buffer = ""
        self._fragment_type = ""
        self._fragment_open_tag = ""
        self._in_code_fence = False

    def feed(self, token: str) -> None:
        """Consume one model token without exposing private XML."""
        if not token:
            return
        if self._fragment_type:
            self._consume_fragment(token)
            return
        self._text_buffer += token
        match = self._find_ui_open()
        if match is None:
            if "<" not in self._text_buffer:
                self._emit_text(self._text_buffer)
                self._text_buffer = ""
                return
            keep = len('<ui type="research-map">')
            safe = max(0, len(self._text_buffer) - keep)
            if safe:
                self._emit_text(self._text_buffer[:safe])
                self._text_buffer = self._text_buffer[safe:]
            return
        if match.start():
            self._emit_text(self._text_buffer[:match.start()])
        self._fragment_type = match.group("type")
        self._fragment_open_tag = match.group(0)
        if self._on_fragment_start is not None:
            self._on_fragment_start(self._fragment_type)
        self._fragment_buffer = self._text_buffer[match.end():]
        self._text_buffer = ""
        self._consume_fragment("")

    def finish(self) -> None:
        """Flush plain text and fail an unterminated private fragment.

        The swallowed fragment text is salvaged back into the markdown stream:
        models sometimes reference the tag in prose (e.g. inside inline code),
        and discarding the buffer would truncate the answer mid-sentence.
        """
        if self._fragment_type:
            self._on_error("UI fragment ended before its closing tag")
            self._emit_text(self._fragment_open_tag + self._fragment_buffer)
            self._fragment_buffer = self._fragment_type = self._fragment_open_tag = ""
        if self._text_buffer:
            self._emit_text(self._text_buffer)
            self._text_buffer = ""

    def _find_ui_open(self) -> re.Match[str] | None:
        """Find the next tag that is outside Markdown fenced code."""
        for match in _OPEN_UI.finditer(self._text_buffer):
            fences_before = self._text_buffer[:match.start()].count("```")
            if self._in_code_fence ^ bool(fences_before % 2):
                continue
            return match
        return None

    def _emit_text(self, text: str) -> None:
        if not text:
            return
        self._in_code_fence ^= bool(text.count("```") % 2)
        self._on_text(text)

    def _consume_fragment(self, token: str) -> None:
        self._fragment_buffer += token
        if len(self._fragment_buffer.encode("utf-8")) > _MAX_FRAGMENT_BYTES:
            self._on_error("UI fragment exceeded the size limit")
            self._fragment_buffer = self._fragment_type = self._fragment_open_tag = ""
            return
        close = self._fragment_buffer.find(_CLOSE_UI)
        if close < 0:
            return
        raw_xml = self._fragment_buffer[:close]
        remainder = self._fragment_buffer[close + len(_CLOSE_UI):]
        fragment = parse_ui_fragment(self._fragment_type, raw_xml)
        self._fragment_buffer = self._fragment_type = self._fragment_open_tag = ""
        if fragment is None:
            self._on_error("UI fragment did not match its registered schema")
        else:
            self._on_fragment(fragment)
        if remainder:
            self.feed(remainder)


def parse_ui_fragment(fragment_type: str, raw_xml: str) -> PresentationDecision | None:
    """Map one complete XML subtree to a safe product DTO."""
    if fragment_type != "research-map":
        return None
    try:
        root = ElementTree.fromstring(raw_xml.strip())
    except ElementTree.ParseError:
        return None
    if root.tag != "map" or set(root.attrib) != {"title"} or len(root) != 1:
        return None
    title = root.attrib["title"].strip()
    node = _parse_node(root[0])
    if not title or node is None:
        return None
    try:
        decision = ResearchMapDecision.model_validate({"title": title, "root": node})
    except ValidationError:
        return None
    return PresentationDecision(
        type=fragment_type,
        payload=decision.model_dump(exclude={"kind"}),
        raw_xml=raw_xml.strip(),
    )


def _parse_node(element: ElementTree.Element) -> dict[str, Any] | None:
    if element.tag != "node" or set(element.attrib) != {"label"}:
        return None
    label = element.attrib["label"].strip()
    if not label:
        return None
    children: list[dict[str, Any]] = []
    citations: list[str] = []
    for child in element:
        if child.tag == "node":
            parsed = _parse_node(child)
            if parsed is None:
                return None
            children.append(parsed)
        elif child.tag == "evidence" and set(child.attrib) == {"ref"} and not list(child):
            reference = child.attrib["ref"].strip()
            if not reference:
                return None
            citations.append(reference)
        else:
            return None
    result: dict[str, Any] = {"label": label, "children": children}
    if citations:
        result["citation_ids"] = list(dict.fromkeys(citations))
    return result


__all__ = [
    "A2UIFragmentStreamParser",
    "PresentationDecision",
    "ResearchMapDecision",
    "parse_ui_fragment",
]
