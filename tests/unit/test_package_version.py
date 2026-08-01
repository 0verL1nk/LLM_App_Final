from __future__ import annotations

from pathlib import Path
import tomllib

from agent import __version__


def test_runtime_version_matches_package_metadata() -> None:
    project_root = Path(__file__).resolve().parents[2]
    package_metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == package_metadata["project"]["version"]
