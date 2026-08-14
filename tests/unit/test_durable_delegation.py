from pathlib import Path

from agent.adapters.orm.run_repository import create_run, list_run_items
from agent.adapters.orm.task_query_repository import get_agent_task
from agent.application.delegation_service import submit_delegated_agent_task


def test_delegate_task_creates_one_durable_task_and_item(tmp_path: Path) -> None:
    database = str(tmp_path / "delegation.sqlite")
    run, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-1",
        prompt="核验论文",
        db_name=database,
    )
    task, created = submit_delegated_agent_task(
        run_uid=run["run_uid"],
        tool_call_id="call-1",
        role="researcher",
        description="核验实验设置",
        db_name=database,
    )

    persisted = get_agent_task(task_uid=task["task_uid"], db_name=database)
    assert created is True
    assert persisted is not None
    assert persisted["agent_role"] == "researcher"
    assert persisted["input"] == {
        "objective": "核验实验设置",
        "coordination_mode": "join",
        "tool_call_id": "call-1",
    }
    assert list_run_items(run_uid=run["run_uid"], db_name=database) == [
        {
            "id": f"item_agent_task_{task['task_uid']}",
            "taskId": task["task_uid"],
            "type": "agent_task",
            "status": "in_progress",
            "payload": {"agent": "researcher", "task": "核验实验设置", "summary": "已加入任务队列"},
            "createdAt": list_run_items(run_uid=run["run_uid"], db_name=database)[0]["createdAt"],
            "updatedAt": list_run_items(run_uid=run["run_uid"], db_name=database)[0]["updatedAt"],
        }
    ]
