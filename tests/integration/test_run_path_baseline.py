"""Baseline confirmation of the active durable web Run path before further edits.

These tests document, via executable assertions, the run path, worker
implementation, queue configuration and ``paper_leader_profile`` middleware that
are actually in effect (openspec change durable-research-agent-runtime, task 0).
They must keep passing while the migration continues; a failure means a
documented baseline behavior changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel

from agent.adapters.orm.run_repository import get_run as repository_get_run
from agent.adapters.orm.run_repository import list_run_events as repository_list_run_events
from agent.adapters.orm.run_repository import list_run_items as repository_list_run_items
from agent.adapters.orm.task_query_repository import get_agent_task
from agent.application import research_workspace, run_execution
from agent.application.execution_routing import resolve_execution_route
from agent.application.research_workspace import research_workspace_service
from agent.application.task_delivery import dispatch_task
from agent.application.task_worker_host import TaskOutboxWorker
from agent.middlewares.builder import build_middleware_list
from agent.middlewares.durable_delegation import DurableDelegationMiddleware
from agent.middlewares.llm_logger import llm_logger_middleware
from agent.middlewares.plan import plan_middleware
from agent.middlewares.trace import TraceMiddleware
from agent.profiles import paper_leader_profile, profile_for_execution_mode
from agent.session_factory import AgentDependencies
from api.main import app

USER_UUID = "baseline-user"
PROJECT_UID = "baseline-project"
SESSION_UID = "baseline-session"
FINAL_ANSWER = "This is the durable runtime baseline answer."

_DB_WRAPPED_RUN_REPOSITORY_FUNCTIONS = (
    "create_leader_run",
    "update_run_status",
    "append_run_lifecycle_event",
)
_DB_WRAPPED_RUN_EXECUTION_FUNCTIONS = (
    "claim_run_execution",
    "get_run",
    "get_run_item",
    "append_run_lifecycle_event",
    "append_run_item_event",
    "update_run_status",
)
_DB_WRAPPED_STEERING_FUNCTIONS = (
    "delivered_steering_inputs",
    "move_unconfirmed_inputs_to_followup",
    "queue_steering_input",
    "unconfirmed_steering_inputs",
)


class _BindableFakeChatModel(FakeListChatModel):
    """FakeListChatModel cannot bind tools; the runtime agent requires binding."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_BindableFakeChatModel":
        return self


class _EvidenceStub:
    def search_text(self, query: str) -> str:
        return query

    def search(self, query: str) -> dict[str, Any]:
        return {"query": query, "evidences": []}

    def list_documents(self) -> list[dict[str, Any]]:
        return []

    def read_document(self, doc_id: str, offset: int, limit: int) -> tuple[str, int]:
        return ("", 0)


def _wrap_database(monkeypatch, module: Any, names: tuple[str, ...], database: str) -> None:
    for name in names:
        monkeypatch.setattr(module, name, _db_bound(getattr(module, name), database))


def _db_bound(original: Any, database: str) -> Any:
    def wrapped(**kwargs: Any) -> Any:
        return original(**kwargs, db_name=database)

    return wrapped


def _capture_leader(create_leader_run: Any, captured: list[dict[str, Any]], **kwargs: Any) -> Any:
    result = create_leader_run(**kwargs)
    captured.append(result[1])
    return result


def _prepare_workspace(monkeypatch, tmp_path: Path, database: str) -> list[dict[str, Any]]:
    """Point the real service at a disposable database and a deterministic model."""
    persisted_messages: list[dict[str, Any]] = []
    monkeypatch.setenv("CHECKPOINTER_DB_PATH", str(tmp_path / "checkpoints.sqlite"))
    research_workspace_service.invalidate_user(USER_UUID)

    _wrap_database(monkeypatch, research_workspace, _DB_WRAPPED_RUN_REPOSITORY_FUNCTIONS, database)
    _wrap_database(monkeypatch, run_execution, _DB_WRAPPED_RUN_EXECUTION_FUNCTIONS, database)
    _wrap_database(monkeypatch, research_workspace, _DB_WRAPPED_STEERING_FUNCTIONS, database)
    monkeypatch.setattr(
        research_workspace,
        "require_project",
        lambda **_kwargs: {"project_uid": PROJECT_UID, "project_name": "基线项目"},
    )
    monkeypatch.setattr(research_workspace, "list_project_sessions", lambda **_kwargs: [{"session_uid": SESSION_UID}])
    monkeypatch.setattr(research_workspace, "list_project_files", lambda **_kwargs: [])
    monkeypatch.setattr(
        research_workspace,
        "list_project_session_messages",
        lambda **_kwargs: list(persisted_messages),
    )
    monkeypatch.setattr(
        research_workspace,
        "save_project_session_messages",
        lambda **kwargs: persisted_messages.extend(kwargs["messages"]),
    )
    monkeypatch.setattr(research_workspace, "read_api_key_for_user", lambda **_kwargs: "baseline-key")
    monkeypatch.setattr(research_workspace, "read_model_name_for_user", lambda **_kwargs: "baseline-model")
    monkeypatch.setattr(research_workspace, "read_base_url_for_user", lambda **_kwargs: None)
    monkeypatch.setattr(
        research_workspace,
        "DynamicProjectEvidenceService",
        lambda **_kwargs: _EvidenceStub(),
    )
    monkeypatch.setattr(
        research_workspace,
        "build_openai_compatible_chat_model",
        lambda **_kwargs: _BindableFakeChatModel(responses=[FINAL_ANSWER] * 8),
    )
    monkeypatch.setattr(research_workspace, "search_project_memory_items", lambda **_kwargs: [])
    monkeypatch.setattr(research_workspace, "enqueue_turn_memory_consolidation", lambda **_kwargs: None)
    monkeypatch.setattr(research_workspace, "enqueue_session_title_generation", lambda **_kwargs: None)
    monkeypatch.setattr(research_workspace, "durable_agent_tasks_enabled", lambda **_kwargs: False)
    from agent.middlewares import builder as middleware_builder

    # Production default: the flag is off, so leader sessions build without
    # delegation; keep the disposable database away from the default one.
    monkeypatch.setattr(middleware_builder, "durable_agent_tasks_enabled", lambda **_kwargs: False)
    import agent.adapters as agent_adapters

    monkeypatch.setattr(
        agent_adapters,
        "get_or_create_thread_id_for_session",
        lambda **_kwargs: "baseline-thread-1",
    )
    return persisted_messages


def test_web_run_path_surface_and_paper_leader_profile_middleware() -> None:
    """The web Run path is the durable POST /runs contract with the leader profile."""
    api_routes: dict[str, set[str]] = {}
    for route in app.routes:
        if hasattr(route, "methods"):
            api_routes.setdefault(route.path, set()).update(route.methods or ())
    runs_path = "/api/v1/projects/{project_uid}/sessions/{session_uid}/runs"
    assert "POST" in api_routes[runs_path]
    assert "GET" in api_routes["/api/v1/runs/{run_uid}/events"]
    assert "GET" in api_routes["/api/v1/runs/{run_uid}/items"]

    # The comparison/review route resolves to the paper_leader profile.
    route = resolve_execution_route(prompt="对比两篇论文的证据", requested_mode="auto")
    assert route.resolved_mode == "agent_teams"
    assert profile_for_execution_mode("agent_teams") is paper_leader_profile
    assert paper_leader_profile.middleware_ids == ("trace", "llm_logger", "subagent", "plan")

    # Delegation middleware is cohort-gated by DURABLE_AGENT_TASKS_ENABLED.
    middleware = build_middleware_list(
        model=_BindableFakeChatModel(responses=["ok"]),
        profile=paper_leader_profile,
        deps=AgentDependencies(search_document_fn=lambda query: query),
        enable_auto_summarization=False,
        enable_tool_selector=False,
    )
    assert not any(isinstance(item, DurableDelegationMiddleware) for item in middleware)
    assert any(isinstance(item, TraceMiddleware) for item in middleware)
    assert plan_middleware in middleware
    assert middleware[-1] is llm_logger_middleware


def test_paper_leader_delegation_middleware_requires_feature_flag(monkeypatch) -> None:
    monkeypatch.setenv("DURABLE_AGENT_TASKS_ENABLED", "true")
    middleware = build_middleware_list(
        model=_BindableFakeChatModel(responses=["ok"]),
        profile=paper_leader_profile,
        deps=AgentDependencies(search_document_fn=lambda query: query),
        enable_auto_summarization=False,
        enable_tool_selector=False,
    )
    delegation = next(item for item in middleware if isinstance(item, DurableDelegationMiddleware))
    assert [tool.name for tool in delegation.tools] == ["delegate_task"]
    assert "researcher" in delegation.system_prompt


def test_queue_configuration_and_transport_modes(monkeypatch) -> None:
    """Local transport nudges the shared queue; outbox leaves work to the worker."""
    from utils import task_queue

    enqueued: list[dict[str, Any]] = []

    def _fake_enqueue(_func: Any, **kwargs: Any) -> dict[str, Any]:
        enqueued.append(kwargs)
        return {"mode": "queued", "job_id": None}

    monkeypatch.setattr(task_queue, "enqueue_background_task", _fake_enqueue)
    monkeypatch.delenv("PAPERSAGE_TASK_TRANSPORT", raising=False)

    result = dispatch_task(task_uid="task-queue-check")

    assert result == {"mode": "queued", "job_id": None}
    assert enqueued == [{"task_uid": "task-queue-check"}]

    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "outbox")
    assert dispatch_task(task_uid="task-queue-check") is None

    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "invalid")
    try:
        dispatch_task(task_uid="task-queue-check")
        raise AssertionError("invalid transport must fail hard")
    except ValueError as exc:
        assert "PAPERSAGE_TASK_TRANSPORT" in str(exc)

    # Default local queue size is bounded and shared with ingestion/title work.
    monkeypatch.delenv("LOCAL_TASK_MAX_WORKERS", raising=False)
    assert task_queue.LOCAL_TASK_MAX_WORKERS == 2


def test_web_run_dispatch_executes_through_outbox_worker_and_items(monkeypatch, tmp_path: Path) -> None:
    """POST /run semantics: API records Run+Task+outbox; the worker owns execution."""
    database = str(tmp_path / "run-path.sqlite")
    persisted_messages = _prepare_workspace(monkeypatch, tmp_path, database)
    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "outbox")
    delivery_calls: list[str] = []
    leader_tasks: list[dict[str, Any]] = []
    unwrapped_create_leader_run = research_workspace.create_leader_run
    monkeypatch.setattr(
        research_workspace,
        "create_leader_run",
        lambda **kwargs: _capture_leader(unwrapped_create_leader_run, leader_tasks, **kwargs),
    )

    run = research_workspace_service.prepare_turn_run(
        project_uid=PROJECT_UID,
        session_uid=SESSION_UID,
        user_uuid=USER_UUID,
        prompt="Summarize the baseline document",
        client_request_id="baseline-request-1",
        execution_mode="agent_teams",
        enqueue_task_delivery_fn=lambda task_uid: delivery_calls.append(task_uid)
        or dispatch_task(task_uid=task_uid),
    )
    run_uid = str(run["run_uid"])
    leader_task_uid = str(leader_tasks[0]["task_uid"])

    persisted_run = repository_get_run(run_uid=run_uid, user_uuid=USER_UUID, db_name=database)
    assert persisted_run is not None
    assert persisted_run["status"] == "queued"
    assert persisted_run["resolved_mode"] == "agent_teams"
    task = get_agent_task(task_uid=leader_task_uid, db_name=database)
    assert task is not None
    assert task["kind"] == "leader"
    assert task["status"] == "queued"
    # The outbox transport no-ops in API processes: work stays pending for workers.
    assert delivery_calls == [leader_task_uid]

    worker = TaskOutboxWorker(worker_id="baseline-worker", db_name=database)
    outcome = worker.run_once()
    assert outcome.status == "delivered"
    assert str(outcome.task_outcome.task_uid) == leader_task_uid
    assert outcome.task_outcome.status == "completed"
    assert worker.run_once().status == "idle"

    completed = repository_get_run(run_uid=run_uid, user_uuid=USER_UUID, db_name=database)
    assert completed is not None
    assert completed["status"] == "completed"
    assert get_agent_task(task_uid=leader_task_uid, db_name=database)["status"] == "completed"

    events = repository_list_run_events(run_uid=run_uid, db_name=database)
    event_types = [event["eventType"] for event in events]
    assert event_types[0] == "run.created"
    assert event_types[1] == "run.started"
    assert event_types[-1] == "run.completed"
    sequences = [event["sequence"] for event in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))

    items = repository_list_run_items(run_uid=run_uid, db_name=database)["items"]
    answer = next(item for item in items if item["type"] == "assistant_message")
    assert answer["status"] == "completed"
    assert FINAL_ANSWER in str(answer["payload"].get("text"))
    assistant = next(message for message in reversed(persisted_messages) if message.get("role") == "assistant")
    assert assistant["content"] == FINAL_ANSWER


def test_sse_replay_after_reconnect_returns_only_later_events(monkeypatch, tmp_path: Path) -> None:
    """A reconnecting browser resumes from its last applied sequence in order."""
    database = str(tmp_path / "reconnect.sqlite")
    _prepare_workspace(monkeypatch, tmp_path, database)
    monkeypatch.setenv("PAPERSAGE_TASK_TRANSPORT", "outbox")

    run = research_workspace_service.prepare_turn_run(
        project_uid=PROJECT_UID,
        session_uid=SESSION_UID,
        user_uuid=USER_UUID,
        prompt="Replay check",
        client_request_id="baseline-request-2",
        execution_mode="react",
        enqueue_task_delivery_fn=lambda task_uid: None,
    )
    run_uid = str(run["run_uid"])
    worker = TaskOutboxWorker(worker_id="baseline-worker", db_name=database)
    assert worker.run_once().status == "delivered"

    from api import run_routes

    _wrap_database(
        monkeypatch,
        run_routes,
        ("get_run", "list_run_events", "list_run_items", "expire_stalled_runs"),
        database,
    )
    client = TestClient(app)
    frames = _read_sse_frames(client, run_uid, after_seq=0)
    replayed = [event["eventType"] for event in frames]
    assert replayed[0] == "run.created"
    assert replayed[-1] == "run.completed"

    midpoint = max(1, len(frames) // 2)
    cursor = int(frames[midpoint - 1]["sequence"])
    resumed = _read_sse_frames(client, run_uid, after_seq=cursor)
    assert [event["sequence"] for event in resumed] == [event["sequence"] for event in frames[midpoint:]]
    assert resumed[0]["eventId"] == frames[midpoint]["eventId"]


def _read_sse_frames(client: TestClient, run_uid: str, *, after_seq: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with client.stream(
        "GET",
        f"/api/v1/runs/{run_uid}/events",
        params={"afterSeq": after_seq},
        headers={"X-User-Id": USER_UUID},
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    return events
