"""Architecture freeze on legacy multi-agent machinery in the canonical path.

The durable-research-agent-runtime proposal forbids restoring A2A, TeamRuntime,
ThreadPoolExecutors or in-process global task tables (Non-goals), and freezes
new use of the legacy thread-pool queue outside its sanctioned dev-transport
adapter. These tests fail when a new import reintroduces any of them.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "agent"

# Modules that must never be imported from agent/ (deleted legacy machinery).
BANNED_PATH_COMPONENTS = ("team", "a2a")
BANNED_IMPORTED_NAMES = ("TeamRuntime", "build_delegation_execution", "A2A")
BANNED_IMPORT_PREFIXES = ("concurrent.futures", "multiprocessing")

# The legacy local thread queue may only be touched by its existing consumers.
TASK_QUEUE_ALLOWED_IMPORTERS = frozenset(
    {
        "agent/application/agent_center/memory.py",
        "agent/application/session_titles.py",
        "agent/application/task_delivery.py",
    }
)

# Durable task authority must live in the database, never module globals.
NO_MODULE_GLOBAL_CONTAINERS = frozenset(
    {
        "agent/application/delegation_service.py",
        "agent/application/leader_task_executor.py",
        "agent/application/research_workspace.py",
        "agent/application/steering_inputs.py",
        "agent/application/subagent_task_executor.py",
        "agent/application/task_delivery.py",
        "agent/application/task_dispatcher.py",
        "agent/application/task_worker_host.py",
    }
)
_MUTABLE_CALL_NAMES = {"dict", "list", "set"}


@dataclass(frozen=True)
class _ImportFact:
    module: str
    names: tuple[str, ...]


def _agent_python_files() -> list[Path]:
    return [path for path in sorted(AGENT_ROOT.rglob("*.py")) if "__pycache__" not in path.parts]


def _imports(tree: ast.Module) -> list[_ImportFact]:
    facts: list[_ImportFact] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            facts.extend(_ImportFact(alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            facts.append(_ImportFact(node.module, tuple(alias.name for alias in node.names)))
    return facts


def test_agent_modules_never_import_legacy_team_or_a2a_machinery() -> None:
    violations: list[str] = []
    for path in _agent_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fact in _imports(tree):
            components = fact.module.split(".")
            if any(component in BANNED_PATH_COMPONENTS for component in components):
                violations.append(f"{path.relative_to(ROOT)} imports legacy module {fact.module}")
            if fact.module.startswith(BANNED_IMPORT_PREFIXES):
                violations.append(f"{path.relative_to(ROOT)} imports banned pool module {fact.module}")
            for name in fact.names:
                if name in BANNED_IMPORTED_NAMES:
                    violations.append(f"{path.relative_to(ROOT)} imports banned symbol {name}")
    assert not violations, "Legacy A2A/TeamRuntime/pool imports are frozen: " + "; ".join(violations)


def test_agent_modules_cannot_directly_use_the_legacy_thread_queue() -> None:
    importers = set()
    for path in _agent_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fact in _imports(tree):
            if fact.module == "utils.task_queue" or fact.module.startswith("utils.task_queue."):
                importers.add(path.relative_to(ROOT).as_posix())
    assert importers == set(TASK_QUEUE_ALLOWED_IMPORTERS), (
        "New agent modules must dispatch through agent.application.task_delivery instead of "
        f"utils.task_queue. Importers: {sorted(importers)}"
    )


def test_durable_task_authority_modules_own_no_module_global_containers() -> None:
    violations: list[str] = []
    for relative in sorted(NO_MODULE_GLOBAL_CONTAINERS):
        path = ROOT / relative
        if not path.exists():
            violations.append(f"{relative} no longer exists; update NO_MODULE_GLOBAL_CONTAINERS")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name) or target.id.startswith("__"):
                    continue
                if isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
                    violations.append(f"{relative}: module-level mutable container {target.id}")
                elif (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in _MUTABLE_CALL_NAMES
                ):
                    violations.append(f"{relative}: module-level mutable container {target.id}")
    assert not violations, (
        "Durable task authority lives in the database, not process globals: " + "; ".join(violations)
    )


def test_frozen_module_list_matches_agent_layout() -> None:
    """The frozen authority list must stay in sync with the real package layout."""
    existing = {
        path.relative_to(ROOT).as_posix()
        for path in _agent_python_files()
        if path.parent == AGENT_ROOT / "application"
    }
    listed = set(NO_MODULE_GLOBAL_CONTAINERS)
    assert listed <= existing, f"Stale frozen-module entries: {sorted(listed - existing)}"


def test_legacy_team_directory_is_not_recreated() -> None:
    for name in BANNED_PATH_COMPONENTS:
        legacy_dir = AGENT_ROOT / name
        python_files = list(legacy_dir.rglob("*.py")) if legacy_dir.exists() else []
        assert not python_files, f"agent/{name}/ is deleted legacy machinery and must not return"
