from agent.application.evals import load_eval_cases

FIXTURE_PATH = "tests/evals/fixtures/agent_task_eval_set_v1.jsonl"


def test_agent_task_eval_fixture_has_broad_project_and_web_case_coverage() -> None:
    cases = load_eval_cases(FIXTURE_PATH)

    assert len(cases) >= 19
    categories = {item.category for item in cases}
    assert {
        "project_rag",
        "project_compare",
        "project_scope_boundary",
        "project_gap",
        "web_research",
        "web_tradeoff",
        "hybrid_research",
        "hybrid_rollout",
        "hybrid_guardrail",
        "hybrid_reject",
        "project_contradiction",
        "project_false_premise",
        "project_abstain",
        "web_overturn",
        "routing_discrimination",
        "project_delegation_scaling",
    }.issubset(categories)


def test_agent_task_eval_fixture_uses_judge_rubrics_and_stable_process_contracts() -> None:
    cases = load_eval_cases(FIXTURE_PATH)
    hybrid_case = next(item for item in cases if item.case_id == "hybrid_research_001")
    boundary_case = next(item for item in cases if item.case_id == "project_scope_boundary_001")
    rollout_case = next(item for item in cases if item.case_id == "hybrid_rollout_001")

    assert hybrid_case.final_answer_contract.success_rubric
    assert hybrid_case.process_contract.requires_evidence is True
    assert hybrid_case.process_contract.required_tool_names == ["delegate_task"]
    assert boundary_case.process_contract.required_tool_names == ["search_document"]
    assert rollout_case.process_contract.require_plan is True
    assert rollout_case.process_contract.min_execution_completion_ratio == 1.0
    assert hybrid_case.process_contract.required_subagent_types == ["researcher"]
    assert hybrid_case.process_contract.min_delegation_count == 2
    assert hybrid_case.process_contract.require_parallel_delegation is True


def test_agent_task_eval_fixture_balances_access_modes_with_forbidden_tool_contracts() -> None:
    cases = load_eval_cases(FIXTURE_PATH)
    abstain_case = next(item for item in cases if item.case_id == "project_abstain_001")
    local_route_case = next(item for item in cases if item.case_id == "routing_discrimination_local_001")
    web_route_case = next(item for item in cases if item.case_id == "routing_discrimination_web_001")
    scaling_case = next(item for item in cases if item.case_id == "project_delegation_scaling_001")

    assert abstain_case.process_contract.forbidden_tool_names == ["search_web"]
    assert abstain_case.process_contract.requires_evidence is False
    assert local_route_case.process_contract.forbidden_tool_names == ["search_web"]
    assert web_route_case.process_contract.required_tool_names == ["search_web"]
    assert web_route_case.process_contract.forbidden_tool_names == []
    assert scaling_case.process_contract.min_evidence_count == 8
    assert scaling_case.process_contract.required_subagent_types == ["researcher"]
    assert scaling_case.process_contract.min_delegation_count == 2
    assert scaling_case.process_contract.require_parallel_delegation is True



def test_default_task_eval_fixture_avoids_brittle_phase_label_contracts() -> None:
    cases = load_eval_cases(FIXTURE_PATH)

    assert all(item.process_contract.required_phase_labels == [] for item in cases)
