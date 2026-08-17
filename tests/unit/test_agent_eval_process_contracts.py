from types import SimpleNamespace

from agent.application.evals import (
    AgentEvalCase,
    FinalAnswerJudgeResult,
    build_eval_report,
    evaluate_case_result,
    run_agent_evals,
)


def _parallel_delegation_case() -> AgentEvalCase:
    return AgentEvalCase.from_dict(
        {
            "id": "delegation_001",
            "category": "project_compare",
            "prompt": "请比较两篇论文并给出建议",
            "success_rubric": "Answer should compare both papers and give a recommendation.",
            "requires_evidence": True,
            "min_evidence_count": 2,
            "required_tool_names": ["delegate_task"],
            "required_subagent_types": ["researcher", "reviewer"],
            "min_delegation_count": 2,
            "require_parallel_delegation": True,
        }
    )


def _delegation_turn_result(output_messages: list[object]) -> dict[str, object]:
    return {
        "answer": "RAG 更适合当前阶段 <evidence>chunk-1|p1|o0-10</evidence> <evidence>chunk-2|p2|o0-10</evidence>",
        "evidence_items": [{"chunk_id": "chunk-1"}, {"chunk_id": "chunk-2"}],
        "output_messages": output_messages,
        "phase_path": "处理中 -> 输出最终答案",
        "trace_payload": [],
        "run_latency_ms": 5.0,
    }


def _passing_judge(*_args: object, **_kwargs: object) -> FinalAnswerJudgeResult:
    return FinalAnswerJudgeResult(passed=True, score=0.9, reasoning="pass")


def test_evaluate_case_result_passes_parallel_delegation_in_single_message() -> None:
    turn_result = _delegation_turn_result(
        [
            SimpleNamespace(
                content="",
                tool_calls=[
                    {"name": "delegate_task", "args": {"role": "researcher", "description": "检索 RAG"}},
                    {"name": "delegate_task", "args": {"role": "reviewer", "description": "审阅 Self-RAG"}},
                ],
            )
        ]
    )

    result = evaluate_case_result(_parallel_delegation_case(), turn_result, judge=_passing_judge)

    assert result["completed"] is True
    assert result["process_checks"]["subagent_types_passed"] is True
    assert result["process_checks"]["delegation_count"] == 2
    assert result["process_checks"]["parallel_delegation_passed"] is True
    assert result["process_checks"]["max_delegations_per_message"] == 2
    assert result["diagnostics"]["total_tool_calls"] == 2


def test_evaluate_case_result_rejects_sequential_delegation_as_parallel() -> None:
    turn_result = _delegation_turn_result(
        [
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "delegate_task", "args": {"role": "researcher", "description": "检索"}}],
            ),
            SimpleNamespace(
                content="",
                tool_calls=[{"name": "delegate_task", "args": {"role": "reviewer", "description": "审阅"}}],
            ),
        ]
    )

    result = evaluate_case_result(_parallel_delegation_case(), turn_result, judge=_passing_judge)

    assert result["process_checks"]["delegation_count"] == 2
    assert result["process_checks"]["subagent_types_passed"] is True
    assert result["process_checks"]["max_delegations_per_message"] == 1
    assert result["process_checks"]["parallel_delegation_passed"] is False
    assert result["completed"] is False
    assert "prompt" in result["feedback"]["remediation_area"]
    assert "delegation contract" in result["feedback"]["failure_reason"]


def test_evaluate_case_result_ignores_legacy_task_tool_delegation_facts() -> None:
    turn_result = _delegation_turn_result(
        [
            SimpleNamespace(
                content="",
                tool_calls=[
                    {"name": "task", "args": {"subagent_type": "researcher"}},
                    {"name": "task", "args": {"subagent_type": "reviewer"}},
                ],
            )
        ]
    )

    result = evaluate_case_result(_parallel_delegation_case(), turn_result, judge=_passing_judge)

    assert result["process_checks"]["used_tool_names"] == ["task"]
    assert result["process_checks"]["delegation_count"] == 0
    assert result["process_checks"]["delegated_subagent_types"] == []
    assert result["process_checks"]["parallel_delegation_passed"] is False


def test_evaluate_case_result_flags_forbidden_tool_usage() -> None:
    case = AgentEvalCase.from_dict(
        {
            "id": "forbidden_001",
            "category": "routing_discrimination",
            "prompt": "只基于当前项目文档回答问题",
            "success_rubric": "Answer should rely on project documents only.",
            "requires_evidence": True,
            "min_evidence_count": 1,
            "required_tool_names": ["search_document"],
            "forbidden_tool_names": ["search_web"],
        }
    )

    turn_result = {
        "answer": "结论 <evidence>chunk-1|p1|o0-10</evidence>",
        "evidence_items": [{"chunk_id": "chunk-1"}],
        "output_messages": [
            SimpleNamespace(
                tool_calls=[
                    {"name": "search_document", "args": {"query": "q"}},
                    {"name": "search_web", "args": {"query": "q"}},
                ]
            )
        ],
        "phase_path": "处理中 -> 输出最终答案",
        "trace_payload": [],
        "run_latency_ms": 5.0,
    }

    result = evaluate_case_result(case, turn_result, judge=_passing_judge)

    assert result["process_checks"]["tool_names_passed"] is True
    assert result["process_checks"]["forbidden_tools_passed"] is False
    assert result["process_checks"]["forbidden_tools_used"] == ["search_web"]
    assert result["completed"] is False
    assert "forbidden tools" in result["feedback"]["failure_reason"]


def test_evaluate_case_result_passes_when_forbidden_tools_absent() -> None:
    case = AgentEvalCase.from_dict(
        {
            "id": "forbidden_pass_001",
            "category": "routing_discrimination",
            "prompt": "只基于当前项目文档回答问题",
            "success_rubric": "Answer should rely on project documents only.",
            "requires_evidence": True,
            "min_evidence_count": 1,
            "required_tool_names": ["search_document"],
            "forbidden_tool_names": ["search_web"],
        }
    )

    turn_result = {
        "answer": "结论 <evidence>chunk-1|p1|o0-10</evidence>",
        "evidence_items": [{"chunk_id": "chunk-1"}],
        "output_messages": [
            SimpleNamespace(tool_calls=[{"name": "search_document", "args": {"query": "q"}}])
        ],
        "phase_path": "处理中 -> 输出最终答案",
        "trace_payload": [],
        "run_latency_ms": 5.0,
    }

    result = evaluate_case_result(case, turn_result, judge=_passing_judge)

    assert result["process_checks"]["forbidden_tools_passed"] is True
    assert result["process_checks"]["forbidden_tools_used"] == []
    assert result["completed"] is True


def test_build_eval_report_records_run_config_provenance() -> None:
    report = build_eval_report(
        fixture_path="tests/evals/fixtures/agent_task_eval_set_v1.jsonl",
        case_results=[],
        run_config={"runner_mode": "live_model", "agent_model": "qwen-plus"},
    )

    assert report["run_config"]["runner_mode"] == "live_model"
    assert report["run_config"]["agent_model"] == "qwen-plus"


def test_build_eval_report_defaults_run_config_to_empty_dict() -> None:
    report = build_eval_report(
        fixture_path="tests/evals/fixtures/agent_task_eval_set_v1.jsonl",
        case_results=[],
    )

    assert report["run_config"] == {}


def test_run_agent_evals_records_crashed_case_and_continues() -> None:
    def _case(case_id: str) -> AgentEvalCase:
        return AgentEvalCase.from_dict(
            {
                "id": case_id,
                "category": "fact",
                "prompt": "请总结",
                "success_rubric": "Answer should summarize.",
            }
        )

    call_counts = {"boom": 0}

    class _FlakyRunner:
        def __call__(self, case: AgentEvalCase) -> dict[str, object]:
            if case.case_id == "boom":
                call_counts["boom"] += 1
                raise RuntimeError("Agent stream ended without a final state")
            return {
                "answer": "结论 <evidence>chunk-1|p1|o0-10</evidence>",
                "evidence_items": [{"chunk_id": "chunk-1"}],
                "output_messages": [
                    SimpleNamespace(tool_calls=[{"name": "search_document", "args": {}}])
                ],
                "phase_path": "处理中 -> 输出最终答案",
                "trace_payload": [],
                "run_latency_ms": 5.0,
            }

    report = run_agent_evals(
        [_case("boom"), _case("ok")],
        runner=_FlakyRunner(),
        judge=lambda *_args, **_kwargs: FinalAnswerJudgeResult(
            passed=True, score=0.9, reasoning="pass"
        ),
    )

    assert call_counts["boom"] == 2  # one retry before recording the error
    assert report["total_cases"] == 2
    assert report["completed_cases"] == 1
    boom = next(item for item in report["cases"] if item["case_id"] == "boom")
    assert boom["completed"] is False
    assert "case execution error" in boom["feedback"]["failure_reason"]
    assert boom["diagnostics"]["error_type"] == "RuntimeError"
