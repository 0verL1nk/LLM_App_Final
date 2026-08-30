"""Frozen web-search fixtures for eval runs: record once, replay deterministically.

Replay answers every web query from a versioned fixture file so eval runs
never touch live providers (no 429s, no content drift). Recording captures
live results with write-through persistence; queries that fail live are not
stored, so a later refresh can capture them properly.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from agent.tools import web_search

WEB_FIXTURE_DIR = Path("tests/evals/fixtures/web_snapshots")
FIXTURE_MISS_MARKER = "web_fixture_miss"

_WHITESPACE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    return _WHITESPACE.sub(" ", query.strip().lower())


def fixture_path(name: str) -> Path:
    return WEB_FIXTURE_DIR / f"{name}.json"


def load_fixture(name: str) -> dict[str, dict[str, Any]]:
    path = fixture_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Web fixture '{name}' not found at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, dict):
        raise ValueError(f"Web fixture '{name}' has no entries block.")
    return entries


def checksum(entries: dict[str, Any]) -> str:
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def save_fixture(name: str, entries: dict[str, dict[str, Any]]) -> str:
    path = fixture_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fixture": name,
        "captured_at": datetime.now(UTC).isoformat(),
        "entry_count": len(entries),
        "checksum": checksum(entries),
        "entries": entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload["checksum"]


def activate_replay(name: str) -> str:
    """Route search_web through the fixture; misses surface explicitly."""
    entries = load_fixture(name)

    def _replay(query: str) -> str:
        entry = entries.get(normalize_query(query))
        if entry is None:
            return (
                f"{FIXTURE_MISS_MARKER}: query not captured in fixture '{name}'. "
                "Record or refresh the fixture; replay never falls back to live search."
            )
        return str(entry["text"])

    web_search.set_web_search_override(_replay)
    return checksum(entries)


def activate_record(name: str, *, refresh: bool = False) -> None:
    """Capture live results into the fixture with write-through persistence."""
    if refresh or not fixture_path(name).exists():
        entries: dict[str, dict[str, Any]] = {}
        if fixture_path(name).exists():
            save_fixture(name, entries)
    else:
        entries = load_fixture(name)

    def _record(query: str) -> str:
        provider, text, error = web_search._run_web_search_internal(query)
        if provider is not None and text:
            entries[normalize_query(query)] = {
                "text": text,
                "provider": provider,
                "captured_at": datetime.now(UTC).isoformat(),
            }
            save_fixture(name, entries)
            return text
        # Live failure: surface the error without poisoning the fixture.
        return str(error or "Web search failed during recording.")

    web_search.set_web_search_override(_record)


def deactivate() -> None:
    web_search.set_web_search_override(None)


OverrideHook = Callable[[str], str]
