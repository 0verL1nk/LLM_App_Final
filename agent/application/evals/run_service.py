"""In-app task-completion eval service: run live evals with observable progress.

The service executes the live eval loop on a background thread (never on the
API path) and exposes an in-memory progress registry that the API layer polls.
Report artifacts are also persisted under ``data/evals/`` for inspection.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import AgentEvalCase
from .harness import run_agent_evals
from .live_harness import (
    LivePaperSageEvalRunner,
    build_live_llm_from_env,
    load_project_documents,
)
from .loader import load_eval_cases
from .selection import select_eval_cases

DEFAULT_FIXTURE_PATH = "tests/evals/fixtures/agent_task_eval_set_v1.jsonl"
EVAL_ARTIFACT_DIR = Path("data/evals")
# CLI eval runs persist progress snapshots beside their reports; the service
# surfaces them so the dev evals page shows CLI-started runs too.
CLI_PROGRESS_DIR = Path("docs/plans/baselines")

RunnerFactory = Callable[[], Any]
JudgeFactory = Callable[[], Any]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _case_summary(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("process_checks") or {}
    diagnostics = result.get("diagnostics") or {}
    coverage = result.get("evidence_coverage") or {}
    trials = result.get("trials") or {}
    summary: dict[str, Any] = {
        "completed": bool(result.get("completed")),
        "final_success": bool(result.get("final_success")),
        "process_success": bool(result.get("process_success")),
        "evidence_count": int(coverage.get("count") or 0),
        "evidence_required": int(coverage.get("required_count") or 0),
        "delegation_count": checks.get("delegation_count"),
        "max_delegations_per_message": checks.get("max_delegations_per_message"),
        "run_latency_ms": diagnostics.get("run_latency_ms"),
        "total_tool_calls": diagnostics.get("total_tool_calls"),
        "error_type": diagnostics.get("error_type"),
        "failure_reason": (result.get("feedback") or {}).get("failure_reason"),
    }
    if trials:
        summary["trials"] = trials
    return summary


@dataclass
class _CaseProgress:
    case_id: str
    category: str = ""
    status: str = "pending"  # pending | running | passed | failed | errored
    started_at: str | None = None
    finished_at: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class _EvalRunState:
    uid: str
    fixture_path: str
    trials: int
    status: str = "running"  # running | completed | failed
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    total_cases: int = 0
    case_ids: list[str] = field(default_factory=list)
    cases: dict[str, _CaseProgress] = field(default_factory=dict)
    report: dict[str, Any] | None = None
    artifact_path: str | None = None
    error: str | None = None
    run_config: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        completed_cases = sum(1 for item in self.cases.values() if item.status == "passed")
        finished = sum(1 for item in self.cases.values() if item.status in {"passed", "failed", "errored"})
        return {
            "uid": self.uid,
            "status": self.status,
            "fixture_path": self.fixture_path,
            "trials": self.trials,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_cases": self.total_cases,
            "finished_cases": finished,
            "completed_cases": completed_cases,
            "case_ids": list(self.case_ids),
            "cases": [vars(item) for item in self.cases.values()],
            "report": self.report,
            "artifact_path": self.artifact_path,
            "error": self.error,
        }


class TaskCompletionEvalService:
    """Registry + executor for in-app task-completion eval runs."""

    def __init__(
        self,
        *,
        runner_factory: RunnerFactory | None = None,
        judge_factory: JudgeFactory | None = None,
    ) -> None:
        self._runs: dict[str, _EvalRunState] = {}
        self._lock = threading.Lock()
        self._runner_factory = runner_factory
        self._judge_factory = judge_factory

    def start(
        self,
        *,
        fixture_path: str = DEFAULT_FIXTURE_PATH,
        case_ids: list[str] | None = None,
        limit: int | None = None,
        trials: int = 1,
    ) -> dict[str, Any]:
        cases = select_eval_cases(
            load_eval_cases(fixture_path),
            case_ids=case_ids,
            limit=limit,
        )
        if not cases:
            raise ValueError("No eval cases selected.")
        with self._lock:
            if any(run.status == "running" for run in self._runs.values()):
                raise RuntimeError("An eval run is already in progress.")
            uid = uuid.uuid4().hex[:12]
            state = _EvalRunState(
                uid=uid,
                fixture_path=fixture_path,
                trials=max(1, int(trials)),
                total_cases=len(cases),
                case_ids=[case.case_id for case in cases],
                cases={
                    case.case_id: _CaseProgress(case_id=case.case_id, category=case.category)
                    for case in cases
                },
            )
            self._runs[uid] = state
        thread = threading.Thread(target=self._execute, args=(state, cases), daemon=True)
        thread.start()
        return state.snapshot()

    def get(self, uid: str) -> dict[str, Any]:
        with self._lock:
            state = self._runs.get(uid)
            if state is not None:
                return state.snapshot()
        for snapshot in self._discover_cli_progress_runs():
            if snapshot.get("uid") == uid:
                return snapshot
        raise KeyError(f"Unknown eval run: {uid}")

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            runs = [state.snapshot() for state in self._runs.values()]
        runs.extend(self._discover_cli_progress_runs())
        return runs

    @staticmethod
    def _discover_cli_progress_runs() -> list[dict[str, Any]]:
        if not CLI_PROGRESS_DIR.is_dir():
            return []
        snapshots: list[dict[str, Any]] = []
        for path in sorted(CLI_PROGRESS_DIR.glob("*.progress.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict) and payload.get("uid"):
                snapshots.append(payload)
        return snapshots

    def _wait_until_settled(self, uid: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
        """Poll until the run leaves the running state (used by tests)."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            snapshot = self.get(uid)
            if snapshot["status"] != "running":
                return snapshot
            time.sleep(0.02)
        raise TimeoutError(f"Eval run {uid} did not settle within {timeout_seconds}s")

    def _execute(self, state: _EvalRunState, cases: list[AgentEvalCase]) -> None:
        try:
            runner = self._runner_factory() if self._runner_factory else self._build_default_runner()
            judge = self._judge_factory() if self._judge_factory else self._build_default_judge()
            state.run_config = {
                "runner_mode": "live_model",
                "trials": state.trials,
                "fixture_path": state.fixture_path,
            }

            def _on_start(case_id: str) -> None:
                with self._lock:
                    progress = state.cases[case_id]
                    progress.status = "running"
                    progress.started_at = _now_iso()

            def _on_result(case_id: str, result: dict[str, Any]) -> None:
                with self._lock:
                    progress = state.cases[case_id]
                    summary = _case_summary(result)
                    progress.summary = summary
                    progress.status = "errored" if summary.get("error_type") else (
                        "passed" if summary.get("completed") else "failed"
                    )
                    progress.finished_at = _now_iso()

            report = run_agent_evals(
                cases,
                runner=runner,
                judge=judge,
                fixture_path=state.fixture_path,
                trials=state.trials,
                run_config=state.run_config,
                on_case_start=_on_start,
                on_case_result=_on_result,
            )
            EVAL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            artifact = EVAL_ARTIFACT_DIR / f"task-completion-{state.uid}.json"
            artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            with self._lock:
                state.report = report
                state.artifact_path = str(artifact)
                state.status = "completed"
                state.finished_at = _now_iso()
        except Exception as exc:
            with self._lock:
                state.status = "failed"
                state.error = f"{type(exc).__name__}: {exc}"
                state.finished_at = _now_iso()

    def _build_default_runner(self) -> LivePaperSageEvalRunner:
        return LivePaperSageEvalRunner(
            llm=build_live_llm_from_env(),
            documents=load_project_documents(),
            project_name="Task Completion Eval",
        )

    def _build_default_judge(self) -> Any:
        from .judges import build_trajectory_llm_as_judge

        return build_trajectory_llm_as_judge(model=build_live_llm_from_env())


task_completion_eval_service = TaskCompletionEvalService()
