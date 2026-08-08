from __future__ import annotations

import json
import tomllib
from pathlib import Path

from agent import __version__


def test_runtime_version_matches_package_metadata() -> None:
    project_root = Path(__file__).resolve().parents[2]
    package_metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == package_metadata["project"]["version"]


def test_runtime_version_matches_desktop_metadata() -> None:
    """A release tag must identify the same Python and Electron product."""
    project_root = Path(__file__).resolve().parents[2]
    desktop_metadata = json.loads((project_root / "web/package.json").read_text(encoding="utf-8"))

    assert __version__ == desktop_metadata["version"]
