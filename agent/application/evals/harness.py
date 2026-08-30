from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from ..contracts import TurnCoreResult
from ..turn_engine import execute_turn_core
from .contracts import AgentEvalCase, FinalAnswerJudge
from .reporting import build_eval_report
from .scoring import evaluate_case_result


@dataclass(frozen=True)
class ExecuteTurnEvalRunner:
    leader_agent: Any
    leader_runtime_config: dict[str, Any]
    search_document_evidence_fn: Any | None = None
    leader_tool_specs: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, case: AgentEvalCase) -> TurnCoreResult:
        return execute_turn_core(
            prompt=case.prompt,
            leader_agent=self.leader_agent,
            leader_runtime_config=dict(self.leader_runtime_config),
            search_document_evidence_fn=self.search_document_evidence_fn,
            leader_tool_specs=list(self.leader_tool_specs),
        )


def _execution_error_case_result(case: AgentEvalCase, exc: Exception) -> dict[str, Any]:
    """Record a crashed case instead of killing the whole eval run."""
    return {
        "case_id": case.case_id,
        "category": case.category,
        "prompt": case.prompt,
        "completed": False,
        "final_success": False,
        "process_success": False,
        "execution_completion_ratio": None,
        "evidence_coverage": {"passed": False, "count": 0, "required_count": 0},
        "final_checks": [],
        "process_checks": {},
        "feedback": {
            "failure_reason": f"case execution error: {type(exc).__name__}: {exc}",
            "feedback_summary": (
                "The case crashed during execution; inspect the error before "
                "treating it as a quality failure."
            ),
            "remediation_area": ["architecture"],
            "recommended_actions": [
                "Inspect the agent stream error for this case and re-run it; "
                "treat it as an infrastructure failure unless reproducible."
            ],
        },
        "answer": "",
        "diagnostics": {"error": str(exc), "error_type": type(exc).__name__},
    }


def _run_single_trial(case: AgentEvalCase, *, runner, judge: FinalAnswerJudge) -> dict[str, Any]:
    try:
        try:
            turn_result = runner(case)
        except Exception:
            # One retry absorbs transient stream/provider failures; a persistent
            # crash is recorded as an errored case so the run keeps going.
            try:
                turn_result = runner(case)
            except Exception as retry_exc:
                return _execution_error_case_result(case, retry_exc)
        try:
            return evaluate_case_result(case, turn_result, judge=judge)
        except Exception:
            # The judge call is equally fallible (429 storms, malformed
            # verdicts): back off briefly, retry once, then record instead of
            # killing the run.
            time.sleep(JUDGE_RETRY_BACKOFF_SECONDS)
            try:
                return evaluate_case_result(case, turn_result, judge=judge)
            except Exception as judge_exc:
                return _execution_error_case_result(case, judge_exc)
    except Exception as exc:  # defensive: a case must never kill the whole run
        return _execution_error_case_result(case, exc)


TRIAL_DELEGATION_KEYS = (
    "delegation_count",
    "max_delegations_per_message",
)

# Backoff before the harness-level judge retry: a 429 storm needs delay, not an
# immediate second hit (SDK-level backoff already ran inside the first attempt).
JUDGE_RETRY_BACKOFF_SECONDS = 2.0


def _combine_trial_results(trial_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Gate a case on pass^k (all trials must pass) and record per-trial detail."""
    combined = dict(trial_results[-1])  # latest trial carries the full detail
    trial_count = len(trial_results)
    passed_trials = sum(1 for item in trial_results if bool(item.get("completed")))
    trial_summary: list[dict[str, Any]] = []
    for index, item in enumerate(trial_results):
        checks = item.get("process_checks") or {}
        diagnostics = item.get("diagnostics") or {}
        summary: dict[str, Any] = {
            "trial": index + 1,
            "completed": bool(item.get("completed")),
            "final_success": bool(item.get("final_success")),
            "process_success": bool(item.get("process_success")),
            "error_type": diagnostics.get("error_type"),
        }
        for key in TRIAL_DELEGATION_KEYS:
            if key in checks:
                summary[key] = checks[key]
        trial_summary.append(summary)
    combined["trials"] = {
        "count": trial_count,
        "passed_trials": passed_trials,
        "success_rate": passed_trials / trial_count if trial_count else 0.0,
        "pass_at_k": passed_trials == trial_count,
        "summary": trial_summary,
    }
    combined["completed"] = passed_trials == trial_count
    combined["final_success"] = all(bool(item.get("final_success")) for item in trial_results)
    combined["process_success"] = all(bool(item.get("process_success")) for item in trial_results)
    if not combined["completed"] and 0 < passed_trials < trial_count:
        feedback = dict(combined.get("feedback") or {})
        feedback["failure_reason"] = (
            f"trial variance: {passed_trials}/{trial_count} trials passed; "
            + str(feedback.get("failure_reason") or "")
        ).strip()
        combined["feedback"] = feedback
    return combined


def run_agent_evals(
    cases: list[AgentEvalCase],
    *,
    runner,
    judge: FinalAnswerJudge | None,
    fixture_path: str = "",
    run_config: dict[str, Any] | None = None,
    trials: int = 1,
    parallel: int = 1,
    on_case_start: Callable[[str], None] | None = None,
    on_case_result: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if judge is None:
        raise ValueError("A final-answer LLM judge is required for task-completion eval runs.")

    normalized_trials = max(1, int(trials))

    def _execute_case(case: AgentEvalCase) -> dict[str, Any]:
        if on_case_start is not None:
            on_case_start(case.case_id)
        trial_results = [
            _run_single_trial(case, runner=runner, judge=judge)
            for _ in range(normalized_trials)
        ]
        combined = trial_results[0] if normalized_trials == 1 else _combine_trial_results(trial_results)
        if on_case_result is not None:
            on_case_result(case.case_id, combined)
        return combined

    workers = max(1, int(parallel))
    if workers == 1:
        case_results = [_execute_case(case) for case in cases]
    else:
        # Results stay in fixture order; progress callbacks fire from worker
        # threads, so registries consuming them must be lock-protected.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            case_results = list(pool.map(_execute_case, cases))
    return build_eval_report(
        fixture_path=fixture_path,
        case_results=case_results,
        run_config=run_config,
    )
