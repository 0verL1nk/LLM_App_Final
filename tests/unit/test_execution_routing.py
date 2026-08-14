from agent.application.execution_routing import resolve_execution_route
from agent.profiles import profile_for_execution_mode


def test_manual_mode_always_wins() -> None:
    route = resolve_execution_route(prompt="请比较三篇论文", requested_mode="react")
    assert route.resolved_mode == "react"
    assert route.reason == "user_selected"


def test_auto_route_selects_team_for_evidence_comparison() -> None:
    route = resolve_execution_route(
        prompt="请对比多篇论文的证据，并审查它们的实验结论。",
        requested_mode="auto",
    )
    assert route.resolved_mode == "agent_teams"


def test_profiles_enforce_mode_capabilities() -> None:
    react = profile_for_execution_mode("react")
    planned = profile_for_execution_mode("plan_execute")
    teams = profile_for_execution_mode("agent_teams")
    assert "planning_pack" not in react.capability_ids
    assert "subagent" not in react.middleware_ids
    assert "planning_pack" in planned.capability_ids
    assert "subagent" not in planned.middleware_ids
    assert "subagent" in teams.middleware_ids
