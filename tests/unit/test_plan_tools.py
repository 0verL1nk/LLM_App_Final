from agent.tools.plan_tools import PlanStep, update_plan


def test_update_plan_creates_revisioned_snapshot() -> None:
    command = update_plan.func(
        revision=0,
        goal="核验论文",
        steps=[PlanStep(id="evidence", title="收集证据")],
        tool_call_id="call-1",
        state={},
    )

    assert command.update["plan"] == {
        "revision": 0,
        "goal": "核验论文",
        "steps": [{"id": "evidence", "title": "收集证据", "status": "pending", "depends_on": [], "lane": "main"}],
    }


def test_update_plan_rejects_stale_revision() -> None:
    command = update_plan.func(
        revision=0,
        goal="核验论文",
        steps=[],
        tool_call_id="call-1",
        state={"plan": {"revision": 0, "goal": "旧计划", "steps": []}},
    )

    assert "revision conflict" in command.update["messages"][0].content


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
