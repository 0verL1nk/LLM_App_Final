from agent.application.execution_routing import (
    MULTI_DOCUMENT_PLAN_THRESHOLD,
    resolve_execution_route,
)
from agent.profiles import profile_for_execution_mode


def test_manual_mode_always_wins() -> None:
    route = resolve_execution_route(prompt="请比较三篇论文", requested_mode="react")
    assert route.resolved_mode == "react"
    assert route.reason == "user_selected"


def test_multi_document_scope_escalates_to_planning() -> None:
    route = resolve_execution_route(
        prompt="总结一下",
        requested_mode="auto",
        document_count=MULTI_DOCUMENT_PLAN_THRESHOLD,
    )
    assert route.resolved_mode == "plan_execute"
    assert route.reason == "multi_document_scope"


def test_single_document_stays_react() -> None:
    route = resolve_execution_route(
        prompt="总结一下",
        requested_mode="auto",
        document_count=1,
    )
    assert route.resolved_mode == "react"
    assert route.reason == "bounded_direct_request"


def test_keywords_alone_never_change_the_mode() -> None:
    """Anti-pseudo-intelligence regression guard: no keyword/length heuristics."""
    comparison_prompt = "请对比多篇论文的证据，并审查它们的实验结论，比较其方法并给出方案分析"
    long_prompt = "请帮我分析研究设计实现一个方案。" * 60

    for prompt in (comparison_prompt, long_prompt):
        route = resolve_execution_route(prompt=prompt, requested_mode="auto")
        assert route.resolved_mode == "react"
        assert route.reason == "bounded_direct_request"


def test_agent_teams_never_auto_assigned() -> None:
    route = resolve_execution_route(
        prompt="对比 审查 比较 review 分别 多篇 对比 证据",
        requested_mode="auto",
        document_count=8,
    )
    assert route.resolved_mode == "plan_execute"


def test_invalid_override_falls_back_to_react() -> None:
    route = resolve_execution_route(prompt="x", requested_mode="turbo")
    assert route.resolved_mode == "react"
    assert route.reason == "invalid_override_fallback"


def test_profiles_enforce_mode_capabilities() -> None:
    react = profile_for_execution_mode("react")
    planned = profile_for_execution_mode("plan_execute")
    teams = profile_for_execution_mode("agent_teams")
    assert "planning_pack" not in react.capability_ids
    assert "subagent" not in react.middleware_ids
    assert "planning_pack" in planned.capability_ids
    assert "subagent" not in planned.middleware_ids
    assert "subagent" in teams.middleware_ids
