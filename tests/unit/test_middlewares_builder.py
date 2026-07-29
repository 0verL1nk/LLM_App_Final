from deepagents.middleware.subagents import SubAgentMiddleware
from langchain_core.language_models import FakeListChatModel

from agent.middlewares.builder import build_middleware_list
from agent.middlewares.llm_logger import llm_logger_middleware
from agent.middlewares.plan import plan_middleware
from agent.middlewares.todolist import todolist_middleware
from agent.profiles import AgentProfile, paper_leader_profile
from agent.session_factory import AgentDependencies


def _deps() -> AgentDependencies:
    return AgentDependencies(search_document_fn=lambda query: query)


def _model() -> FakeListChatModel:
    return FakeListChatModel(responses=["ok"])


def test_leader_runtime_exposes_official_task_subagents_with_bounded_tools() -> None:
    middleware = build_middleware_list(
        model=_model(),
        profile=paper_leader_profile,
        deps=_deps(),
        enable_auto_summarization=False,
        enable_tool_selector=False,
    )

    subagents = next(item for item in middleware if isinstance(item, SubAgentMiddleware))
    tool_names_by_role = {
        spec["name"]: {getattr(tool, "name", "") for tool in spec["tools"]}
        for spec in subagents._subagents
    }

    assert [tool.name for tool in subagents.tools] == ["task"]
    assert tool_names_by_role == {
        "researcher": {"search_document", "search_web", "search_papers", "use_skill"},
        "reviewer": {"search_document", "use_skill"},
        "writer": {"use_skill"},
    }
    assert todolist_middleware in middleware
    assert plan_middleware in middleware


def test_worker_runtime_cannot_recursively_delegate_or_plan() -> None:
    bounded_profile = AgentProfile(
        name="bounded_test_worker",
        description="Test-only bounded profile.",
        prompt_builder=lambda **_kwargs: "bounded",
        capability_ids=("document_pack",),
        middleware_ids=("trace", "llm_logger"),
    )
    middleware = build_middleware_list(
        model=_model(),
        profile=bounded_profile,
        deps=_deps(),
        enable_auto_summarization=False,
        enable_tool_selector=False,
    )

    assert not any(isinstance(item, SubAgentMiddleware) for item in middleware)
    assert todolist_middleware not in middleware
    assert plan_middleware not in middleware
    assert middleware[-1] is llm_logger_middleware
