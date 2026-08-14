from pathlib import Path

from fastapi.testclient import TestClient

from agent.adapters.orm.research_artifact_repository import (
    list_research_artifacts,
    reconcile_evidence_packet_artifacts,
)
from agent.adapters.orm.run_repository import create_run
from agent.adapters.orm.task_attempt_repository import claim_task_by_uid, complete_task_attempt
from agent.adapters.orm.task_dispatch_repository import create_agent_task
from agent.application.task_dispatcher import LeaseTaskWorker
from agent.domain.agent_task import AgentTaskKind
from api.main import app


def test_completed_subagent_persists_one_owned_evidence_artifact(tmp_path: Path) -> None:
    database = str(tmp_path / "artifacts.sqlite")
    run, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="artifact-run",
        prompt="核验方法",
        db_name=database,
    )
    assert created
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="artifact-task",
        input_payload={"objective": "核验方法"},
        db_name=database,
    )
    worker = LeaseTaskWorker(
        worker_id="artifact-worker",
        db_name=database,
        executor=lambda _task: {
            "summary": "实验结果支持该方法。",
            "evidence_refs": ["chunk-1"],
            "evidence": [{"chunk_id": "chunk-1", "doc_uid": "doc-1", "page_no": 2}],
        },
    )

    assert worker.run_task(str(task["task_uid"])).status == "completed"
    artifacts = list_research_artifacts(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        db_name=database,
    )

    assert len(artifacts) == 1
    assert artifacts[0]["task_uid"] == task["task_uid"]
    assert artifacts[0]["evidence_refs"] == ["chunk-1"]
    assert artifacts[0]["content"]["evidence"][0]["page_no"] == 2
    assert list_research_artifacts(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="other-user",
        db_name=database,
    ) == []


def test_reconciliation_backfills_packet_after_completion_crash_window(tmp_path: Path) -> None:
    database = str(tmp_path / "artifact-reconciliation.sqlite")
    run, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="artifact-reconcile",
        prompt="核验方法",
        db_name=database,
    )
    assert created
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key="artifact-reconcile-task",
        db_name=database,
    )
    claimed = claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id="worker", db_name=database)
    assert claimed is not None
    assert complete_task_attempt(
        task_uid=str(task["task_uid"]),
        attempt_uid=str(claimed["current_attempt_uid"]),
        result={"summary": "已完成", "evidence_refs": ["chunk-1"]},
        db_name=database,
    )

    assert reconcile_evidence_packet_artifacts(db_name=database) == [task["task_uid"]]
    assert reconcile_evidence_packet_artifacts(db_name=database) == []


def test_artifact_route_enforces_run_owner_scope(monkeypatch, tmp_path: Path) -> None:
    database = str(tmp_path / "artifact-route.sqlite")
    run, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="artifact-route",
        prompt="核验方法",
        db_name=database,
    )
    assert created
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]), kind=AgentTaskKind.SUBAGENT, idempotency_key="artifact-route-task", db_name=database
    )
    claimed = claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id="worker", db_name=database)
    assert claimed is not None
    assert complete_task_attempt(
        task_uid=str(task["task_uid"]), attempt_uid=str(claimed["current_attempt_uid"]), result={"summary": "已完成"}, db_name=database
    )
    assert reconcile_evidence_packet_artifacts(db_name=database) == [task["task_uid"]]

    from api import runtime_task_routes

    original = runtime_task_routes.list_research_artifacts
    monkeypatch.setattr(runtime_task_routes, "list_research_artifacts", lambda **kwargs: original(**kwargs, db_name=database))
    client = TestClient(app)
    response = client.get("/api/v1/projects/project-1/sessions/session-1/research-artifacts", headers={"X-User-Id": "user-1"})
    forbidden = client.get("/api/v1/projects/project-1/sessions/session-1/research-artifacts", headers={"X-User-Id": "user-2"})

    assert response.status_code == 200
    assert response.json()["data"][0]["task_uid"] == task["task_uid"]
    assert forbidden.json()["data"] == []
