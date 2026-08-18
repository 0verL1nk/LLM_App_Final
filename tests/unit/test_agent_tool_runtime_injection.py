"""Regression tests for ToolRuntime injection through the real agent stack.

``update_plan`` and ``delegate_task`` depend on langchain_core recognizing the
``runtime: ToolRuntime`` parameter as injected. Stringified annotations (from
``from __future__ import annotations``) break that detection, and the tools then
crash with ``missing 1 required positional argument: 'runtime'`` at call time.
These tests execute the tools through the real ``create_agent`` path so both the
injection wiring and any annotation regressions fail loudly here.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent.profiles import paper_leader_profile
from agent.session_factory import AgentDependencies, AgentRuntimeOptions, create_agent_session


class ScriptedToolCallingModel(BaseChatModel):
    """Replays scripted messages; supports bind_tools so agent wiring works."""

    script: list[Any] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = self.script.pop(0) if self.script else AIMessage(content="完成")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedToolCallingModel":
        return self

    @property
    def _llm_type(self) -> str:
        return "scripted"


def test_plan_and_delegation_tools_execute_with_runtime_injection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHECKPOINTER_DB_PATH", str(tmp_path / "checkpoints.db"))
    llm = ScriptedToolCallingModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "update_plan",
                        "args": {
                            "revision": 0,
                            "goal": "比较两篇论文",
                            "steps": [{"id": "s1", "title": "检索证据"}],
                        },
                        "id": "c1",
                        "type": "tool_call",
                    },
                    {
                        "name": "delegate_task",
                        "args": {"role": "researcher", "description": "检索 RAG"},
                        "id": "c2",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(content="完成"),
        ]
    )
    session = create_agent_session(
        profile=paper_leader_profile,
        deps=AgentDependencies(search_document_fn=lambda _query: ""),
        options=AgentRuntimeOptions(llm=llm, project_name="P", scope_summary="S"),
    )
    try:
        result = session.agent.invoke(
            {"messages": [{"role": "user", "content": "测试"}]},
            config=dict(session.runtime_config),
        )
    finally:
        session.close()

    assert result.get("plan") is not None
    assert result["plan"]["goal"] == "比较两篇论文"
    tool_results = [
        str(getattr(message, "content", ""))
        for message in result["messages"]
        if getattr(message, "type", "") == "tool"
    ]
    assert any("Plan revision 0 saved" in content for content in tool_results)
    # The turn-level harness has no durable run context, so delegation must
    # return its clean machine-readable error instead of crashing.
    assert any("durable_run_required" in content for content in tool_results)
