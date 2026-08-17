from __future__ import annotations

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


def run_agent_evals(
    cases: list[AgentEvalCase],
    *,
    runner,
    judge: FinalAnswerJudge | None,
    fixture_path: str = "",
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if judge is None:
        raise ValueError("A final-answer LLM judge is required for task-completion eval runs.")

    case_results: list[dict[str, Any]] = []
    for case in cases:
        try:
            turn_result = runner(case)
        except Exception:
            # One retry absorbs transient stream/provider failures; a persistent
            # crash is recorded as an errored case so the run keeps going.
            try:
                turn_result = runner(case)
            except Exception as retry_exc:
                case_results.append(_execution_error_case_result(case, retry_exc))
                continue
        case_results.append(evaluate_case_result(case, turn_result, judge=judge))
    return build_eval_report(
        fixture_path=fixture_path,
        case_results=case_results,
        run_config=run_config,
    )
