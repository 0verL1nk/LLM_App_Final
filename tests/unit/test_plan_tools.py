from types import SimpleNamespace
from typing import Any

from agent.tools.plan_tools import PlanStep, read_plan, update_plan


def _runtime(state: dict) -> SimpleNamespace:
    return SimpleNamespace(tool_call_id="call-1", state=state)


def test_update_plan_creates_revisioned_snapshot() -> None:
    command = update_plan.func(
        runtime=_runtime({}),
        revision=0,
        goal="核验论文",
        steps=[PlanStep(id="evidence", title="收集证据")],
    )

    assert command.update["plan"] == {
        "revision": 0,
        "goal": "核验论文",
        "steps": [{"id": "evidence", "title": "收集证据", "status": "pending", "depends_on": [], "lane": "main"}],
    }


def test_update_plan_rejects_stale_revision() -> None:
    command = update_plan.func(
        runtime=_runtime({"plan": {"revision": 0, "goal": "旧计划", "steps": []}}),
        revision=0,
        goal="核验论文",
        steps=[],
    )

    assert "revision conflict" in command.update["messages"][0].content


def test_read_plan_reports_no_active_plan() -> None:
    assert "No active plan" in read_plan.func(runtime=_runtime({}))


def test_read_plan_returns_current_snapshot() -> None:
    assert "核验论文" in read_plan.func(
        runtime=_runtime({"plan": {"revision": 0, "goal": "核验论文", "steps": []}})
    )


def test_update_plan_validates_dependency_ids() -> None:
    try:
        update_plan.args_schema.model_validate(
            {
                "revision": 0,
                "goal": "核验论文",
                "steps": [{"id": "a", "title": "步骤", "depends_on": ["missing"]}],
            }
        )
    except ValueError as exc:
        assert "dependencies" in str(exc)
    else:
        raise AssertionError("Expected dependency validation failure")


def test_plan_nudge_injects_via_system_message_when_retrieval_runs_planless(monkeypatch) -> None:
    from types import SimpleNamespace

    from agent.middlewares.plan import PLAN_NUDGE_MARKER, PlanMiddleware

    monkeypatch.setenv("AGENT_PLAN_NUDGE_ENABLED", "1")

    ai_with_search = SimpleNamespace(
        type="ai", content="", tool_calls=[{"name": "search_document", "args": {"query": "q"}}]
    )
    captured: dict[str, Any] = {}

    class _Request:
        state = {"messages": [ai_with_search], "plan": None}
        system_message = None

        def override(self, **kwargs):
            return SimpleNamespace(system_message=kwargs.get("system_message"))

    def _handler(req):
        message = getattr(req, "system_message", None)
        captured["text"] = str(getattr(message, "content", message))
        return SimpleNamespace()

    PlanMiddleware().wrap_model_call(_Request(), _handler)

    assert PLAN_NUDGE_MARKER in captured["text"]


def test_plan_nudge_skips_when_plan_exists_or_no_retrieval() -> None:
    from types import SimpleNamespace

    from agent.middlewares.plan import PlanMiddleware

    plain = SimpleNamespace(type="ai", content="hi", tool_calls=[])
    for state in (
        {"messages": [plain], "plan": {"steps": []}},
        {"messages": [plain], "plan": None},
    ):
        seen: list[Any] = []

        class _Request:
            pass

        _Request.state = state
        _Request.system_message = "base"

        def _override(**kwargs):
            raise AssertionError("override must not be called when the nudge skips")

        _Request.override = _override

        def _handler(req):
            seen.append(req)

        PlanMiddleware().wrap_model_call(_Request(), _handler)
        assert seen and seen[0].system_message == "base"
