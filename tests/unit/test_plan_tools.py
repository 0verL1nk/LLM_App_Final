from types import SimpleNamespace

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
