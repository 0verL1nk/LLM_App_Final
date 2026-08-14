"""Repository-level development-rule checks used locally and in CI."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_CODE_LINES = 500
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".cjs",
    ".mjs",
    ".css",
    ".go",
    ".sh",
    ".ps1",
    ".nsh",
}
BASELINE_PATH = ROOT / "scripts" / "code_size_baseline.json"


def tracked_code_files() -> list[Path]:
    """Return version-controlled source files, excluding ignored generated output."""
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        ROOT / relative_path
        for relative_path in result.stdout.splitlines()
        if (ROOT / relative_path).is_file() and (ROOT / relative_path).suffix.lower() in CODE_EXTENSIONS
    ]


def line_count(path: Path) -> int:
    """Count source lines using the repository's UTF-8 text convention."""
    return len(path.read_text(encoding="utf-8").splitlines())


def load_size_baseline() -> dict[str, int]:
    """Load the explicit legacy-size ceiling until each file is split."""
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    files = payload.get("legacy_over_limit_files")
    if not isinstance(files, dict):
        raise ValueError("code_size_baseline.json must contain legacy_over_limit_files")
    return {str(path): int(limit) for path, limit in files.items()}


def check_code_size() -> list[str]:
    """Reject new oversize files and growth of registered legacy debt."""
    baseline = load_size_baseline()
    failures: list[str] = []
    observed_legacy: set[str] = set()
    for path in tracked_code_files():
        relative_path = path.relative_to(ROOT).as_posix()
        lines = line_count(path)
        if lines <= MAX_CODE_LINES:
            continue
        ceiling = baseline.get(relative_path)
        if ceiling is None:
            failures.append(f"{relative_path}: {lines} lines exceeds {MAX_CODE_LINES}; split by responsibility")
            continue
        observed_legacy.add(relative_path)
        if lines > ceiling:
            failures.append(
                f"{relative_path}: {lines} lines exceeds its debt baseline of {ceiling}; it may only shrink"
            )
    stale_entries = sorted(set(baseline) - observed_legacy)
    for relative_path in stale_entries:
        failures.append(f"{relative_path}: remove resolved entry from code_size_baseline.json")
    return failures


def check_path_hacks() -> list[str]:
    """Reject runtime import-path mutation outside isolated test fixtures."""
    failures: list[str] = []
    for path in tracked_code_files():
        relative_path = path.relative_to(ROOT).as_posix()
        if relative_path.startswith("tests/") or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        if any(_is_sys_path_insert(node) for node in ast.walk(tree)):
            failures.append(f"{relative_path}: sys.path.insert is prohibited in production code")
    return failures


def _is_sys_path_insert(node: ast.AST) -> bool:
    """Identify the ``sys.path.insert(...)`` call without matching documentation text."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    target = node.func.value
    return (
        node.func.attr == "insert"
        and isinstance(target, ast.Attribute)
        and target.attr == "path"
        and isinstance(target.value, ast.Name)
        and target.value.id == "sys"
    )


def main() -> int:
    """Run every repository-wide rule and return a CI-compatible status code."""
    parser = argparse.ArgumentParser(description="Validate PaperSage repository development rules")
    parser.add_argument("--check", action="store_true", help="Run all repository checks")
    args = parser.parse_args()
    if not args.check:
        parser.error("use --check")
    failures = [*check_code_size(), *check_path_hacks()]
    if not failures:
        print("Repository development rules passed.")
        return 0
    print("Repository development rule violations:", file=sys.stderr)
    print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
