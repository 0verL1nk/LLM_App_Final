"""Tests for the model-call progressive nudges (plan + reviewer).

Nudges ride the single provider-facing system message via wrap_model_call -
tool results are never mutated because they carry JSON payloads (the v1
tool-result approach corrupted search_document evidence and was reverted).
"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, SystemMessage

from agent.middlewares.durable_delegation import (
    REVIEWER_NUDGE_MARKER,
    DurableDelegationMiddleware,
)
from agent.middlewares.plan import PLAN_NUDGE_MARKER, PlanMiddleware
from agent.subagent.loader import SubAgentDefinition


def _model_request(state: dict, system_message: object = None) -> SimpleNamespace:
    request = SimpleNamespace(state=state, system_message=system_message)

    def override(**kwargs):
        return SimpleNamespace(state=state, system_message=kwargs.get("system_message"))

    request.override = override
    return request


def _search_call_message() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_document", "args": {"query": "q"}, "id": "c1"}],
    )


def _sent_system_text(request: SimpleNamespace, captured: dict) -> None:
    captured["text"] = str(
        getattr(request.system_message, "content", request.system_message) or ""
    )


def test_plan_nudge_injected_when_retrieval_runs_planless(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_PLAN_NUDGE_ENABLED", "1")
    captured: dict[str, str] = {}
    state = {"messages": [_search_call_message()], "plan": None}

    def handler(req):
        _sent_system_text(req, captured)
        return SimpleNamespace()

    PlanMiddleware().wrap_model_call(_model_request(state), handler)

    assert PLAN_NUDGE_MARKER in captured["text"]


def test_plan_nudge_skipped_when_plan_exists_or_no_retrieval(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_PLAN_NUDGE_ENABLED", "1")
    plain = AIMessage(content="hi", tool_calls=[])

    for state in ({"messages": [plain], "plan": {"goal": "g"}}, {"messages": [plain], "plan": None}):
        passthrough: list[SimpleNamespace] = []

        def handler(req):
            passthrough.append(req)

        PlanMiddleware().wrap_model_call(_model_request(state), handler)
        assert passthrough[0].system_message is None


def test_plan_nudge_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_PLAN_NUDGE_ENABLED", raising=False)
    state = {"messages": [_search_call_message()], "plan": None}
    passthrough: list[SimpleNamespace] = []

    def handler(req):
        passthrough.append(req)

    PlanMiddleware().wrap_model_call(_model_request(state, SystemMessage("base")), handler)

    assert str(passthrough[0].system_message.content) == "base"


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


def _delegate_call(role: str, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "delegate_task", "args": {"role": role}, "id": call_id}],
    )


def test_reviewer_nudge_injected_at_fanout_threshold(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_DELEGATION_NUDGE_ENABLED", "1")
    state = {"messages": [_delegate_call("researcher", "c0")]}
    captured: dict[str, str] = {}

    def handler(req):
        _sent_system_text(req, captured)
        return SimpleNamespace()

    _delegation_middleware().wrap_model_call(_model_request(state), handler)

    assert REVIEWER_NUDGE_MARKER in captured["text"]


def test_reviewer_nudge_skipped_when_reviewer_present_or_below_threshold(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_DELEGATION_NUDGE_ENABLED", "1")

    for state in (
        {"messages": [_delegate_call("reviewer", "c0")]},
        {"messages": []},
    ):
        passthrough: list[SimpleNamespace] = []

        def handler(req):
            passthrough.append(req)

        _delegation_middleware().wrap_model_call(_model_request(state), handler)
        assert passthrough[0].system_message is None


def test_reviewer_nudge_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_DELEGATION_NUDGE_ENABLED", raising=False)
    state = {"messages": [_delegate_call("researcher", "c0")]}
    passthrough: list[SimpleNamespace] = []

    def handler(req):
        passthrough.append(req)

    _delegation_middleware().wrap_model_call(
        _model_request(state, SystemMessage("base")), handler
    )

    assert str(passthrough[0].system_message.content) == "base"
