from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from agent.application.delegation import build_delegation_execution
from agent.profiles import paper_leader_profile
from agent.session_factory import AgentDependencies, AgentRuntimeOptions, create_agent_session
from agent.subagent.loader import load_subagent_definitions


class _QueueChatModel(BaseChatModel):
    responses: list[AIMessage]

    @property
    def _llm_type(self) -> str:
        return "queue-chat-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **_kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        del tools, tool_choice
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **_kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager
        return ChatResult(
            generations=[ChatGeneration(message=self.responses.pop(0))]
        )


def test_subagent_definitions_are_valid_and_deterministic() -> None:
    definitions = load_subagent_definitions()

    assert [definition.name for definition in definitions] == ["researcher", "reviewer", "writer"]
    assert all(definition.description for definition in definitions)
    assert all(definition.system_prompt for definition in definitions)


def test_parallel_task_calls_are_observed_from_runtime_messages() -> None:
    messages = [
        HumanMessage(content="比较两种方法并审查证据"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "task-research",
                    "name": "task",
                    "args": {"subagent_type": "researcher", "description": "收集证据"},
                    "type": "tool_call",
                },
                {
                    "id": "task-review",
                    "name": "task",
                    "args": {"subagent_type": "reviewer", "description": "独立审查"},
                    "type": "tool_call",
                },
            ],
        ),
        ToolMessage(content="证据结果", tool_call_id="task-research", name="task"),
        ToolMessage(content="审查结果", tool_call_id="task-review", name="task"),
        AIMessage(content="综合结论"),
    ]

    execution = build_delegation_execution(messages)

    assert execution["enabled"] is True
    assert execution["rounds"] == 1
    assert execution["member_count"] == 2
    assert execution["roles"] == ["researcher", "reviewer"]
    assert all(task["parallel_requested"] for task in execution["tasks"])
    assert not any(task["parallel"] for task in execution["tasks"])
    assert [task["status"] for task in execution["tasks"]] == ["completed", "completed"]


def test_canonical_supervisor_executes_real_subagent_task(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHECKPOINTER_DB_PATH", str(tmp_path / "checkpoints.db"))
    model = _QueueChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "task-research",
                        "name": "task",
                        "args": {
                            "subagent_type": "researcher",
                            "description": "收集证据",
                        },
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="研究结果"),
            AIMessage(content="综合结论"),
        ]
    )
    session = create_agent_session(
        profile=paper_leader_profile,
        deps=AgentDependencies(search_document_fn=lambda _query: "文档证据"),
        options=AgentRuntimeOptions(
            llm=model,
            enable_tool_selector=False,
            thread_id="supervisor-e2e",
        ),
    )

    try:
        result = session.agent.invoke(
            {"messages": [HumanMessage(content="研究并总结")]},
            config=session.runtime_config,
        )
    finally:
        session.close()

    execution = build_delegation_execution(result["messages"])
    assert execution["roles"] == ["researcher"]
    assert execution["tasks"][0]["status"] == "completed"
    assert execution["tasks"][0]["output"] == "研究结果"
    assert result["messages"][-1].content == "综合结论"
