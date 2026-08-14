from pathlib import Path

from agent.adapters.orm.task_dispatch_repository import create_leader_run
from agent.adapters.orm.task_query_repository import get_agent_task
from agent.application import leader_task_executor


def test_leader_task_executes_the_persisted_run_input_once(tmp_path: Path, monkeypatch) -> None:
    database = str(tmp_path / "leader-worker.sqlite")
    run, leader, _ = create_leader_run(
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
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(leader_task_executor, "execute_research_run", lambda **kwargs: calls.append(kwargs))

    leader_task_executor.execute_leader_task(task_uid=str(leader["task_uid"]), db_name=database)
    leader_task_executor.execute_leader_task(task_uid=str(leader["task_uid"]), db_name=database)

    assert calls == [
        {
            "run_uid": str(run["run_uid"]),
            "project_uid": "project-1",
            "session_uid": "session-1",
                "user_uuid": "user-1",
                "prompt": "比较两篇论文",
                "leader_task_uid": str(leader["task_uid"]),
                "steering_initial_delivery": False,
                "resolved_mode": "agent_teams",
        }
    ]
    persisted = get_agent_task(task_uid=str(leader["task_uid"]), db_name=database)
    assert persisted is not None
    assert persisted["status"] == "completed"
