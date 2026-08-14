from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock, Thread

from agent.adapters.orm.task_dispatch_repository import (
    claim_next_task_outbox,
    create_agent_task,
    create_leader_run,
    get_task_outbox,
    reclaim_expired_task_outbox_claims,
)
from agent.adapters.orm.task_query_repository import get_agent_task
from agent.application import task_worker_host
from agent.domain.agent_task import AgentTaskKind


def _leader(database: str) -> tuple[dict[str, object], dict[str, object]]:
    run, leader, _created = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="比较两篇论文",
        input_payload={
            "project_uid": "project-1",
            "session_uid": "session-1",
            "user_uuid": "user-1",
            "prompt": "比较两篇论文",
        },
        db_name=database,
    )
    return run, leader


def test_outbox_claim_is_recoverable_and_acknowledged_after_delivery(tmp_path: Path) -> None:
    database = str(tmp_path / "outbox.sqlite")
    _run, leader = _leader(database)
    outbox = claim_next_task_outbox(worker_id="publisher-a", db_name=database)

    assert outbox is not None
    assert outbox["task_uid"] == leader["task_uid"]
    assert claim_next_task_outbox(worker_id="publisher-b", db_name=database) is None
    reclaimed = reclaim_expired_task_outbox_claims(
        now=datetime.now(UTC) + timedelta(seconds=61),
        db_name=database,
    )
    assert reclaimed == [outbox["outbox_uid"]]
    replay = claim_next_task_outbox(worker_id="publisher-b", db_name=database)
    assert replay is not None


def test_worker_host_executes_and_acknowledges_a_leader_delivery(tmp_path: Path, monkeypatch) -> None:
    database = str(tmp_path / "host.sqlite")
    run, leader = _leader(database)
    calls: list[str] = []

    def execute(task: dict[str, object]) -> dict[str, object]:
        calls.append(str(task["task_uid"]))
        return {"summary": "完成"}

    monkeypatch.setattr(task_worker_host, "execute_leader_task_payload", execute)
    host = task_worker_host.TaskOutboxWorker(worker_id="worker-1", db_name=database)

    outcome = host.run_once()

    assert outcome.status == "delivered"
    assert calls == [leader["task_uid"]]
    task = get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)
    assert task is not None and task["status"] == "completed"
    published = get_task_outbox(outbox_uid=str(outcome.outbox_uid), db_name=database)
    assert published is not None and published["status"] == "published"
    assert run["run_uid"] == task["run_uid"]


def test_worker_executes_a_registered_subagent_task(tmp_path: Path, monkeypatch) -> None:
    database = str(tmp_path / "child-not-claimed.sqlite")
    run, _leader_task = _leader(database)
    child, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="child-1",
        input_payload={"description": "收集证据"},
        db_name=database,
    )
    monkeypatch.setattr(task_worker_host, "execute_leader_task_payload", lambda _task: {"summary": "完成"})
    monkeypatch.setattr(
        task_worker_host,
        "execute_subagent_task_payload",
        lambda _task, *, definition, db_name: {"summary": f"{definition.name} 完成"},
    )
    # Publish the Leader first so the second poll executes the registered child.
    host = task_worker_host.TaskOutboxWorker(worker_id="worker-1", db_name=database)
    first = host.run_once()
    second = host.run_once()

    assert first.status == "delivered"
    assert second.status == "delivered"
    persisted = get_agent_task(task_uid=str(child["task_uid"]), db_name=database)
    assert persisted is not None and persisted["status"] == "completed"


def test_worker_host_claims_a_registry_extension_kind_without_static_kind_list(tmp_path: Path) -> None:
    database = str(tmp_path / "extension-host.sqlite")
    run, _leader_task = _leader(database)
    extension, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind="compile",
        idempotency_key="compile-1",
        db_name=database,
    )
    host = task_worker_host.TaskOutboxWorker(
        worker_id="worker-1",
        db_name=database,
        executor=task_worker_host.TaskExecutorRegistry(
            kind_executors={"compile": lambda task: {"summary": f"compiled {task['task_uid']}"}}
        ),
    )

    outcome = host.run_once()

    assert outcome.status == "delivered"
    assert outcome.task_outcome is not None and outcome.task_outcome.task_uid == extension["task_uid"]


def test_two_workers_receive_duplicate_delivery_but_execute_one_leader_attempt(tmp_path: Path) -> None:
    """The durable outbox and task lease are the cross-process ownership boundary."""
    database = str(tmp_path / "two-workers.sqlite")
    _run, leader = _leader(database)
    executions: list[str] = []
    outcomes: list[task_worker_host.OutboxDeliveryOutcome] = []
    guard = Lock()
    ready = Barrier(2)

    def execute(task: dict[str, object]) -> dict[str, object]:
        with guard:
            executions.append(str(task["task_uid"]))
        return {"summary": "完成"}

    def poll(worker_id: str) -> None:
        host = task_worker_host.TaskOutboxWorker(
            worker_id=worker_id,
            db_name=database,
            executor=execute,
            task_kinds=(AgentTaskKind.LEADER.value,),
        )
        ready.wait()
        outcome = host.run_once()
        with guard:
            outcomes.append(outcome)

    workers = [Thread(target=poll, args=(f"worker-{index}",)) for index in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert executions == [str(leader["task_uid"])]
    assert sorted(outcome.status for outcome in outcomes) == ["delivered", "idle"]
    persisted = get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)
    assert persisted is not None and persisted["status"] == "completed"


def test_worker_recovers_delivery_abandoned_before_task_lease(tmp_path: Path) -> None:
    """A publisher crash cannot strand a queued task after its outbox lease expires."""
    database = str(tmp_path / "recovered-delivery.sqlite")
    _run, leader = _leader(database)
    abandoned = claim_next_task_outbox(
        worker_id="terminated-worker",
        lease_seconds=1,
        db_name=database,
    )
    assert abandoned is not None
    assert reclaim_expired_task_outbox_claims(
        now=datetime.now(UTC) + timedelta(seconds=2),
        db_name=database,
    ) == [abandoned["outbox_uid"]]

    host = task_worker_host.TaskOutboxWorker(
        worker_id="recovery-worker",
        db_name=database,
        executor=lambda _task: {"summary": "恢复完成"},
        task_kinds=(AgentTaskKind.LEADER.value,),
    )
    outcome = host.run_once()

    assert outcome.status == "delivered"
    assert outcome.task_outcome is not None
    assert outcome.task_outcome.task_uid == leader["task_uid"]
    task = get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)
    assert task is not None and task["status"] == "completed"
