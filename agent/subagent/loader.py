"""Validated file-backed definitions for official Deep Agents subagents."""

import re
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_SUBAGENT_DIR = Path(__file__).resolve().parent
_VALID_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True)
class SubAgentDefinition:
    name: str
    description: str
    system_prompt: str
    capability_ids: tuple[str, ...]
    model: str | None = None
    display_name: str = ""
    """Human-readable label; falls back to ``name`` when absent."""


def load_subagent_definitions(base_dir: str | Path | None = None) -> list[SubAgentDefinition]:
    """Load deterministic, validated subagent definitions from ``agent.md`` files."""
    definitions: list[SubAgentDefinition] = []
    base_path = Path(base_dir) if base_dir is not None else _DEFAULT_SUBAGENT_DIR

    if not base_path.exists():
        return definitions

    for subdir in sorted(base_path.iterdir(), key=lambda item: item.name):
        if not subdir.is_dir() or subdir.name.startswith("__"):
            continue

        config_file = subdir / "agent.md"
        if not config_file.exists():
            continue

        try:
            definitions.append(_parse_agent_md(config_file))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid subagent config {config_file}: {exc}") from exc

    names = [definition.name for definition in definitions]
    if len(names) != len(set(names)):
        raise ValueError("Subagent names must be unique")
    return definitions


def _parse_agent_md(file_path: Path) -> SubAgentDefinition:
    content = file_path.read_text(encoding="utf-8")

    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid agent.md format")

    front_matter = match.group(1)
    system_prompt = match.group(2).strip()

    metadata: dict[str, str] = {}
    for line in front_matter.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    name = metadata.get("name", "").strip()
    description = metadata.get("description", "").strip()
    if not _VALID_NAME.fullmatch(name):
        raise ValueError(f"Invalid subagent name: {name!r}")
    if not description:
        raise ValueError("Subagent description is required")
    if not system_prompt:
        raise ValueError("Subagent system prompt is required")
    capability_ids = tuple(
        item.strip()
        for item in metadata.get("capabilities", "").split(",")
        if item.strip()
    )
    return SubAgentDefinition(
        name=name,
        description=description,
        system_prompt=system_prompt,
        capability_ids=capability_ids,
        model=metadata.get("model", "").strip() or None,
        display_name=metadata.get("display_name", "").strip(),
    )


__all__ = ["SubAgentDefinition", "load_subagent_definitions"]
