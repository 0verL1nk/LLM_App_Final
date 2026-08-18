from pathlib import Path
from types import SimpleNamespace

from agent.adapters.orm.research_plan_repository import (
    get_research_plan,
    link_task_to_plan_step,
    save_plan_snapshot,
)
from agent.adapters.orm.task_attempt_repository import (
    claim_task_by_uid,
    complete_task_attempt,
    mark_task_running,
)
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.domain.agent_task import AgentTaskKind
from agent.middlewares.plan import plan_middleware
from agent.tools.plan_tools import PlanStep, update_plan


def test_linked_plan_step_blocks_then_tracks_task_lifecycle(tmp_path: Path) -> None:
    database = str(tmp_path / "plans.sqlite")
    run, _leader, _created = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="plan-run",
        prompt="Research",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "Research"},
        db_name=database,
    )
    save_plan_snapshot(
        run_uid=str(run["run_uid"]),
        snapshot={
            "revision": 0,
            "goal": "Compare papers",
            "steps": [
                {"id": "sources", "title": "Collect sources", "status": "pending", "depends_on": [], "lane": "research"},
                {"id": "compare", "title": "Compare findings", "status": "pending", "depends_on": ["sources"], "lane": "research"},
            ],
        },
        db_name=database,
    )
    task, _created = create_agent_task(
        run_uid=str(run["run_uid"]),
        parent_task_uid=None,
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="compare-task",
        input_payload={"objective": "Compare findings"},
        db_name=database,
    )
    assert link_task_to_plan_step(run_uid=str(run["run_uid"]), step_id="compare", task_uid=str(task["task_uid"]), db_name=database)
    assert claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id="worker-1", db_name=database) is None

    save_plan_snapshot(
        run_uid=str(run["run_uid"]),
        snapshot={
            "revision": 1,
            "goal": "Compare papers",
            "steps": [
                {"id": "sources", "title": "Collect sources", "status": "completed", "depends_on": [], "lane": "research"},
                {"id": "compare", "title": "Compare findings", "status": "pending", "depends_on": ["sources"], "lane": "research"},
            ],
        },
        db_name=database,
    )
    claimed = claim_task_by_uid(task_uid=str(task["task_uid"]), worker_id="worker-1", db_name=database)
    assert claimed is not None
    attempt_uid = str(claimed["current_attempt_uid"])
    assert mark_task_running(task_uid=str(task["task_uid"]), attempt_uid=attempt_uid, db_name=database)
    running_plan = get_research_plan(run_uid=str(run["run_uid"]), db_name=database)
    assert running_plan is not None
    assert next(step for step in running_plan["steps"] if step["id"] == "compare")["status"] == "in_progress"
    assert complete_task_attempt(task_uid=str(task["task_uid"]), attempt_uid=attempt_uid, result={"summary": "Done"}, db_name=database)
    plan = get_research_plan(run_uid=str(run["run_uid"]), db_name=database)
    assert plan is not None
    compare = next(step for step in plan["steps"] if step["id"] == "compare")
    assert compare["task_uid"] == task["task_uid"]
    assert compare["status"] == "completed"


def test_plan_middleware_persists_leader_update_plan_snapshot(tmp_path: Path) -> None:
    database = str(tmp_path / "plan-tool.sqlite")
    run, _leader, _created = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="plan-tool-run",
        prompt="Research",
        input_payload={"project_uid": "project-1", "session_uid": "session-1", "user_uuid": "user-1", "prompt": "Research"},
        db_name=database,
    )
    command = update_plan.func(
        runtime=SimpleNamespace(tool_call_id="call-1", state={}),
        revision=0,
        goal="Collect evidence",
        steps=[PlanStep(id="evidence", title="Collect evidence")],
    )
    request = SimpleNamespace(
        tool_call={"name": "update_plan", "id": "call-1"},
        runtime=SimpleNamespace(config={"configurable": {"run_uid": run["run_uid"], "task_db_name": database}}),
    )

    assert plan_middleware.wrap_tool_call(request, lambda _request: command) is command
    assert get_research_plan(run_uid=str(run["run_uid"]), db_name=database) == {
        "revision": 0,
        "goal": "Collect evidence",
        "steps": [
            {
                "id": "evidence",
                "title": "Collect evidence",
                "status": "pending",
                "depends_on": [],
                "lane": "main",
                "task_uid": None,
            }
        ],
    }
