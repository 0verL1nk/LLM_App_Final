from types import SimpleNamespace
from typing import Any

from agent.tools.plan_tools import PlanStep, read_plan, update_plan


def _runtime(state: dict) -> SimpleNamespace:
    return SimpleNamespace(tool_call_id="call-1", state=state)


def test_update_plan_creates_revisioned_snapshot() -> None:
    command = update_plan.func(
        tool_call_id="call-1",
        state={},
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
        tool_call_id="call-1",
        state={"plan": {"revision": 0, "goal": "旧计划", "steps": []}},
        revision=0,
        goal="核验论文",
        steps=[],
    )

    assert "revision conflict" in command.update["messages"][0].content


def test_read_plan_reports_no_active_plan() -> None:
    assert "No active plan" in read_plan.func(state={})


def test_read_plan_returns_current_snapshot() -> None:
    assert "核验论文" in read_plan.func(
        state={"plan": {"revision": 0, "goal": "核验论文", "steps": []}}
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
def test_update_plan_tool_call_schema_hides_injected_args() -> None:
    fields = sorted(update_plan.tool_call_schema.model_json_schema().get("properties", {}).keys())
    assert fields == ["goal", "revision", "steps"]


def test_update_plan_runs_through_agent_tool_node() -> None:
    """Regression: the injected args must be supplied by the ToolNode.

    Before the fix the explicit args_schema dropped the InjectedToolCallId /
    InjectedState annotations, so calling update_plan crashed with
    ``missing 2 required positional arguments: 'tool_call_id' and 'state'``
    and failed the whole run (run_2bf2fdfc, 2026-08-16).
    """
    from typing import Any

    from langchain.agents import create_agent
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import BaseTool

    from agent.middlewares.plan import plan_middleware
    from agent.tools.plan_tools import read_plan

    class ScriptedToolModel(BaseChatModel):
        script: list[dict[str, Any]] = []

        def bind_tools(self, tools: list[BaseTool | dict[str, Any]], **kwargs: Any) -> "ScriptedToolModel":
            return self

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: Any = None,
            run_manager: CallbackManagerForLLMRun | None = None,
            **kwargs: Any,
        ) -> ChatResult:
            step = self.script[0] if self.script else {"text": "完成"}
            object.__setattr__(self, "script", self.script[1:])
            message = AIMessage(content=step.get("text", ""), tool_calls=step.get("tool_calls", []))
            return ChatResult(generations=[ChatGeneration(message=message)])

        @property
        def _llm_type(self) -> str:
            return "scripted"

    model = ScriptedToolModel(
        script=[
            {
                "tool_calls": [
                    {
                        "name": "update_plan",
                        "args": {"revision": 0, "goal": "核验论文", "steps": [{"id": "evidence", "title": "收集证据"}]},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ]
            },
            {"text": "完成"},
        ]
    )
    agent = create_agent(
        model=model,
        tools=[update_plan, read_plan],
        system_prompt="test",
        middleware=[plan_middleware],
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "做个计划"}]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_messages, "expected a tool result for update_plan"
    assert "missing" not in str(tool_messages[0].content)
    assert "revision 0 saved" in str(tool_messages[0].content)
    assert result.get("plan", {}).get("revision") == 0
