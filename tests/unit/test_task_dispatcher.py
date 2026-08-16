from pathlib import Path

from agent.adapters.orm.run_repository import create_run, list_run_items
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.adapters.orm.task_query_repository import (
    get_agent_task,
    list_agent_task_attempts,
    request_task_cancel,
)
from agent.application.subagent_task_executor import _sanitize_result
from agent.application.task_dispatcher import (
    LeaseTaskWorker,
    TaskExecutorRegistry,
    run_worker_until_idle,
)
from agent.domain.agent_task import AgentTaskKind


def _create_task(database: str, *, idempotency_key: str) -> str:
    run, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id=f"request-{idempotency_key}",
        prompt="核验论文",
        db_name=database,
    )
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key=idempotency_key,
        db_name=database,
    )
    return str(task["task_uid"])


def test_lease_worker_persists_executor_result_without_global_state(tmp_path: Path) -> None:
    database = str(tmp_path / "worker.sqlite")
    task_uid = _create_task(database, idempotency_key="result")
    worker = LeaseTaskWorker(
        worker_id="worker-1",
        db_name=database,
        executor=lambda task: {"summary": f"完成 {task['task_uid']}"},
    )

    outcomes = run_worker_until_idle(worker, max_tasks=2)

    assert [outcome.status for outcome in outcomes] == ["completed", "idle"]
    persisted = get_agent_task(task_uid=task_uid, db_name=database)
    assert persisted is not None
    assert persisted["status"] == "completed"
    assert persisted["result"] == {"summary": f"完成 {task_uid}"}
    items = list_run_items(run_uid=str(persisted["run_uid"]), db_name=database)["items"]
    assert items[-1]["taskId"] == task_uid
    assert items[-1]["status"] == "completed"
    assert items[-1]["payload"]["summary"] == f"完成 {task_uid}"


def test_lease_worker_turns_executor_exception_into_failed_task(tmp_path: Path) -> None:
    database = str(tmp_path / "worker.sqlite")
    task_uid = _create_task(database, idempotency_key="failure")

    def fail(_task: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    outcome = LeaseTaskWorker(
        worker_id="worker-1", db_name=database, executor=fail, max_attempts=1
    ).run_once()

    assert outcome.status == "failed"
    persisted = get_agent_task(task_uid=task_uid, db_name=database)
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert persisted["error_message"] == "provider unavailable"
    items = list_run_items(run_uid=str(persisted["run_uid"]), db_name=database)["items"]
    assert items[-1]["status"] == "failed"
    assert items[-1]["payload"]["summary"] == "Agent 任务执行失败"


def test_lease_worker_requeues_transient_failure_with_a_new_outbox(tmp_path: Path) -> None:
    database = str(tmp_path / "retry.sqlite")
    task_uid = _create_task(database, idempotency_key="retry")

    def fail(_task: dict[str, object]) -> dict[str, object]:
        raise TimeoutError("provider timed out")

    outcome = LeaseTaskWorker(worker_id="worker-1", db_name=database, executor=fail).run_once()

    assert outcome.status == "retrying"
    persisted = get_agent_task(task_uid=task_uid, db_name=database)
    assert persisted is not None
    assert persisted["status"] == "queued"
    attempts = list_agent_task_attempts(task_uid=task_uid, db_name=database)
    assert attempts[0]["error_category"] == "timeout"
    assert attempts[0]["status"] == "failed"


def test_lease_worker_projects_a_safe_boundary_cancellation(tmp_path: Path) -> None:
    database = str(tmp_path / "cancelled-worker.sqlite")
    task_uid = _create_task(database, idempotency_key="cancelled")

    def cancel_while_running(task: dict[str, object]) -> dict[str, object]:
        assert request_task_cancel(task_uid=str(task["task_uid"]), db_name=database)
        return {"summary": "must not become visible"}

    outcome = LeaseTaskWorker(
        worker_id="worker-1", db_name=database, executor=cancel_while_running
    ).run_once()

    assert outcome.status == "cancelled"
    persisted = get_agent_task(task_uid=task_uid, db_name=database)
    items = list_run_items(run_uid=str(persisted["run_uid"]), db_name=database)["items"] if persisted else []
    assert persisted is not None and persisted["status"] == "cancelled"
    assert items[-1]["status"] == "cancelled"
    assert items[-1]["payload"]["summary"] == "Agent 任务已取消"


def test_executor_registry_dynamically_dispatches_by_persisted_kind_and_subagent_role(tmp_path: Path) -> None:
    database = str(tmp_path / "dynamic-worker.sqlite")
    # The repository input is the authority; role selection happens only after claim.
    from agent.adapters.orm.run_repository import create_run
    from agent.adapters.orm.task_dispatch_repository import create_agent_task
    from agent.domain.agent_task import AgentTaskKind

    run, _ = create_run(project_uid="project-2", session_uid="session-2", user_uuid="user-2", client_request_id="dynamic", prompt="任务", db_name=database)
    reviewed, _ = create_agent_task(run_uid=str(run["run_uid"]), kind=AgentTaskKind.SUBAGENT, agent_role="reviewer", idempotency_key="review", db_name=database)
    registry = TaskExecutorRegistry(
        kind_executors={},
        subagent_executors={"reviewer": lambda task: {"summary": f"reviewed {task['task_uid']}"}},
    )
    worker = LeaseTaskWorker(worker_id="worker", db_name=database, executor=registry)

    outcomes = run_worker_until_idle(worker, max_tasks=2)

    assert [outcome.status for outcome in outcomes] == ["completed", "idle"]
    persisted = get_agent_task(task_uid=reviewed["task_uid"], db_name=database)
    assert persisted is not None
    assert persisted["result"] == {"summary": f"reviewed {reviewed['task_uid']}"}


def test_executor_registry_dispatches_a_registered_extension_kind(tmp_path: Path) -> None:
    database = str(tmp_path / "extension-kind.sqlite")
    run, _ = create_run(
        project_uid="project-3",
        session_uid="session-3",
        user_uuid="user-3",
        client_request_id="extension-kind",
        prompt="编译论文",
        db_name=database,
    )
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind="compile",
        idempotency_key="compile-1",
        db_name=database,
    )
    worker = LeaseTaskWorker(
        worker_id="worker",
        db_name=database,
        executor=TaskExecutorRegistry(
            kind_executors={"compile": lambda claimed: {"summary": f"compiled {claimed['task_uid']}"}}
        ),
    )

    outcome = worker.run_task(str(task["task_uid"]))

    assert outcome.status == "completed"
    persisted = get_agent_task(task_uid=str(task["task_uid"]), db_name=database)
    assert persisted is not None
    assert persisted["result"] == {"summary": f"compiled {task['task_uid']}"}


def test_queue_delivery_executes_exact_task_once(tmp_path: Path) -> None:
    database = str(tmp_path / "addressed-worker.sqlite")
    task_uid = _create_task(database, idempotency_key="addressed")
    worker = LeaseTaskWorker(
        worker_id="worker-1",
        db_name=database,
        executor=lambda task: {"summary": f"完成 {task['task_uid']}"},
    )

    first = worker.run_task(task_uid)
    duplicate = worker.run_task(task_uid)

    assert first.status == "completed"
    assert duplicate.status == "idle"


def test_subagent_result_persists_only_the_validated_evidence_packet() -> None:
    result = _sanitize_result(
        {
            "answer": "结论 <evidence>paper:chunk_1|p1</evidence>",
            "evidence_items": [
                {"project_uid": "project-1", "doc_uid": "paper", "chunk_id": "paper:chunk_1"},
                {"project_uid": "other-project", "doc_uid": "paper", "chunk_id": "foreign:chunk"},
            ],
            "run_latency_ms": 12.5,
            "hidden_reasoning": "must never be persisted",
        },
        project_uid="project-1",
        allowed_doc_uids={"paper"},
    )

    assert result == {
        "research_question": "",
        "summary": "结论 <evidence>paper:chunk_1|p1</evidence>",
        "evidence_refs": ["paper:chunk_1"],
        "claims": [],
        "evidence": [
            {
                "chunk_id": "paper:chunk_1",
                "doc_uid": "paper",
                "page_no": None,
                "offset_start": None,
                "offset_end": None,
            }
        ],
        "limitations": [],
        "open_questions": [],
        "metrics": {"run_latency_ms": 12.5},
    }


def test_leader_waits_for_children_without_retaining_an_active_attempt(tmp_path: Path) -> None:
    database = str(tmp_path / "waiting-children.sqlite")
    run, leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="waiting-children",
        prompt="比较论文",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "比较论文"},
        db_name=database,
    )
    child, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        parent_task_uid=str(leader["task_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="child",
        db_name=database,
    )
    worker = LeaseTaskWorker(
        worker_id="worker-1",
        db_name=database,
        executor=lambda _task: {"summary": "等待 child", "waiting_children": True},
    )

    outcome = worker.run_task(str(leader["task_uid"]))

    assert outcome.status == "waiting_children"
    persisted = get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)
    assert persisted is not None
    assert persisted["status"] == "waiting_children"
    assert persisted["current_attempt_uid"] is None
    assert get_agent_task(task_uid=str(child["task_uid"]), db_name=database)["status"] == "queued"
