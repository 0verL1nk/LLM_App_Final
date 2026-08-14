from pathlib import Path

from agent.adapters.orm.runtime_metrics_repository import get_runtime_metrics
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.domain.agent_task import AgentTaskKind


def test_runtime_metrics_are_owner_scoped_and_report_delegation(tmp_path: Path) -> None:
    database = str(tmp_path / "metrics.sqlite")
    run, leader, _created = create_leader_run(
        project_uid="project-1", session_uid="session-1", user_uuid="owner", client_request_id="metrics", prompt="Research",
        input_payload={"prompt": "Research"}, db_name=database,
    )
    create_agent_task(
        run_uid=str(run["run_uid"]), parent_task_uid=str(leader["task_uid"]), kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher", idempotency_key="metrics-child", input_payload={"objective": "Find evidence"}, db_name=database,
    )

    metrics = get_runtime_metrics(user_uuid="owner", db_name=database)
    assert metrics["runs"] == {"queued": 1}
    assert metrics["delegation_count"] == 1
    assert metrics["stalled_runs"] == 0
    assert get_runtime_metrics(user_uuid="other", db_name=database)["runs"] == {}
