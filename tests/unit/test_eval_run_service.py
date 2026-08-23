"""Tests for the eval run service and progress callbacks."""

import threading
from typing import Any

from agent.application.evals import (
    AgentEvalCase,
    FinalAnswerJudgeResult,
    run_agent_evals,
)
from agent.application.evals.run_service import TaskCompletionEvalService


def _case(case_id: str) -> AgentEvalCase:
    return AgentEvalCase.from_dict(
        {
            "id": case_id,
            "category": "fact",
            "prompt": f"问题 {case_id}",
            "success_rubric": "Answer should address the prompt.",
        }
    )


class _StaticRunner:
    def __call__(self, case: AgentEvalCase) -> dict[str, Any]:
        return {
            "answer": f"回答 {case.case_id} <evidence>chunk-1|p1|o0-10</evidence>",
            "evidence_items": [{"chunk_id": "chunk-1"}],
            "output_messages": [
                {"role": "assistant", "tool_calls": [{"name": "search_document", "args": {"query": "q"}}]}
            ],
            "phase_path": "处理中 -> 输出最终答案",
            "trace_payload": [],
            "run_latency_ms": 5.0,
        }


def _passing_judge(*_args: Any, **_kwargs: Any) -> FinalAnswerJudgeResult:
    return FinalAnswerJudgeResult(passed=True, score=0.9, reasoning="pass")


def test_run_agent_evals_reports_start_and_result_callbacks() -> None:
    events: list[tuple[str, str]] = []
    report = run_agent_evals(
        [_case("a"), _case("b")],
        runner=_StaticRunner(),
        judge=_passing_judge,
        on_case_start=lambda case_id: events.append(("start", case_id)),
        on_case_result=lambda case_id, _result: events.append(("result", case_id)),
    )

    assert report["completed_cases"] == 2
    assert events == [
        ("start", "a"),
        ("result", "a"),
        ("start", "b"),
        ("result", "b"),
    ]


def test_run_agent_evals_trials_gate_on_all_trials_passing() -> None:
    calls = {"flaky": 0}

    class _FlakyRunner:
        def __call__(self, case: AgentEvalCase) -> dict[str, Any]:
            if case.case_id == "flaky":
                calls["flaky"] += 1
                return {
                    "answer": "回答" if calls["flaky"] % 2 == 1 else "跑偏的回答",
                    "evidence_items": [],
                    "phase_path": "输出最终答案",
                    "trace_payload": [],
                    "run_latency_ms": 1.0,
                }
            return _StaticRunner()(case)

    def _judge(case: AgentEvalCase, normalized: dict[str, Any]) -> FinalAnswerJudgeResult:
        passed = "跑偏" not in str(normalized.get("answer"))
        return FinalAnswerJudgeResult(passed=passed, score=0.9 if passed else 0.1, reasoning="r")

    report = run_agent_evals(
        [_case("flaky")],
        runner=_FlakyRunner(),
        judge=_judge,
        trials=3,
    )

    flaky = report["cases"][0]
    assert calls["flaky"] == 3
    assert flaky["completed"] is False  # pass^3: 偶数次失败即不通过
    assert flaky["trials"]["count"] == 3
    assert flaky["trials"]["success_rate"] > 0
    assert "trial variance" in flaky["feedback"]["failure_reason"]


def test_run_agent_evals_parallel_keeps_fixture_order_and_reports_all_callbacks() -> None:
    events: list[tuple[str, str]] = []
    report = run_agent_evals(
        [_case("a"), _case("b"), _case("c")],
        runner=_StaticRunner(),
        judge=_passing_judge,
        parallel=2,
        on_case_start=lambda case_id: events.append(("start", case_id)),
        on_case_result=lambda case_id, _result: events.append(("result", case_id)),
    )

    assert report["completed_cases"] == 3
    assert [case["case_id"] for case in report["cases"]] == ["a", "b", "c"]
    assert sorted(events) == sorted(
        [("start", key) for key in "abc"] + [("result", key) for key in "abc"]
    )


def test_eval_service_runs_to_completion_with_injected_factories() -> None:
    service = TaskCompletionEvalService(
        runner_factory=_StaticRunner,
        judge_factory=lambda: _passing_judge,
    )
    fixture = "tests/evals/fixtures/agent_task_eval_set_v1.jsonl"

    snapshot = service.start(fixture_path=fixture, case_ids=["project_rag_fact_001"])

    assert snapshot["status"] == "running"
    assert snapshot["total_cases"] == 1

    final = service._wait_until_settled(snapshot["uid"])
    assert final["status"] == "completed"
    assert final["completed_cases"] == 1
    assert all(item["status"] == "passed" for item in final["cases"])
    assert final["report"]["completion_rate"] == 1.0
    assert final["artifact_path"]


def test_eval_service_rejects_concurrent_runs() -> None:
    release = threading.Event()
    started = threading.Event()

    class _BlockingRunner:
        def __call__(self, case: AgentEvalCase) -> dict[str, Any]:
            started.set()
            release.wait(timeout=5)
            return _StaticRunner()(case)

    service = TaskCompletionEvalService(
        runner_factory=lambda: _BlockingRunner(),
        judge_factory=lambda: _passing_judge,
    )
    fixture = "tests/evals/fixtures/agent_task_eval_set_v1.jsonl"
    service.start(fixture_path=fixture, case_ids=["project_rag_fact_001"])

    assert started.wait(timeout=5)
    try:
        service.start(fixture_path=fixture, case_ids=["project_rag_fact_001"])
    except RuntimeError as exc:
        assert "already in progress" in str(exc)
    else:
        raise AssertionError("Expected concurrent-run rejection")
    finally:
        release.set()
    service._wait_until_settled(service.list_runs()[0]["uid"])
