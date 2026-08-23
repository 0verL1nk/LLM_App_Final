"""Tests for the tool-result progressive nudges (plan + reviewer)."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage

from agent.middlewares.durable_delegation import (
    REVIEWER_NUDGE_MARKER,
    DurableDelegationMiddleware,
)
from agent.middlewares.plan import PLAN_NUDGE_MARKER, PlanMiddleware
from agent.subagent.loader import SubAgentDefinition


def _request(tool_name: str, state: dict) -> SimpleNamespace:
    return SimpleNamespace(
        tool_call={"name": tool_name, "id": "call-1", "args": {}},
        runtime=SimpleNamespace(state=state, config={}),
    )


def _tool_message(content: str = "原始结果") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id="call-1")


def test_plan_nudge_appended_when_retrieval_starts_without_plan() -> None:
    result = PlanMiddleware().wrap_tool_call(
        _request("search_document", {"messages": [], "plan": None}),
        lambda _request: _tool_message(),
    )

    assert PLAN_NUDGE_MARKER in str(result.content)
    assert "原始结果" in str(result.content)


def test_plan_nudge_skipped_when_plan_exists_or_already_given() -> None:
    nudged = ToolMessage(content=f"结果 {PLAN_NUDGE_MARKER} 提示", tool_call_id="x")
    state_with_plan = {"messages": [], "plan": {"goal": "g"}}
    state_nudged = {"messages": [nudged], "plan": None}

    with_plan = PlanMiddleware().wrap_tool_call(
        _request("search_document", state_with_plan), lambda _r: _tool_message()
    )
    already = PlanMiddleware().wrap_tool_call(
        _request("search_document", state_nudged), lambda _r: _tool_message()
    )
    other_tool = PlanMiddleware().wrap_tool_call(
        _request("read_document", {"messages": [], "plan": None}), lambda _r: _tool_message()
    )

    assert PLAN_NUDGE_MARKER not in str(with_plan.content)
    assert PLAN_NUDGE_MARKER not in str(already.content)
    assert PLAN_NUDGE_MARKER not in str(other_tool.content)


def _delegation_middleware() -> DurableDelegationMiddleware:
    definitions = [
        SubAgentDefinition(
            name="researcher",
            description="检索",
            system_prompt="",
            capability_ids=(),
        ),
        SubAgentDefinition(
            name="reviewer",
            description="审阅",
            system_prompt="",
            capability_ids=(),
        ),
    ]
    return DurableDelegationMiddleware(definitions)


def test_reviewer_nudge_after_second_delegation_without_reviewer() -> None:
    prior = AIMessage(
        content="",
        tool_calls=[{"name": "delegate_task", "args": {"role": "researcher"}, "id": "c0"}],
    )
    state = {"messages": [prior]}
    result = _delegation_middleware().wrap_tool_call(
        _request("delegate_task", state), lambda _r: _tool_message()
    )

    assert REVIEWER_NUDGE_MARKER in str(result.content)


def test_reviewer_nudge_skipped_when_reviewer_present_or_below_threshold() -> None:
    with_reviewer = AIMessage(
        content="",
        tool_calls=[{"name": "delegate_task", "args": {"role": "reviewer"}, "id": "c0"}],
    )
    empty_state = {"messages": []}

    skipped_reviewer = _delegation_middleware().wrap_tool_call(
        _request("delegate_task", {"messages": [with_reviewer]}), lambda _r: _tool_message()
    )
    skipped_first = _delegation_middleware().wrap_tool_call(
        _request("delegate_task", empty_state), lambda _r: _tool_message()
    )

    assert REVIEWER_NUDGE_MARKER not in str(skipped_reviewer.content)
    assert REVIEWER_NUDGE_MARKER not in str(skipped_first.content)
