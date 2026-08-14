"""Real interpreter-boundary recovery coverage for durable task leases."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.adapters.orm.run_repository import create_run
from agent.adapters.orm.task_attempt_repository import (
    claim_task_by_uid,
    complete_task_attempt,
    mark_task_running,
    reclaim_expired_task_attempts,
)
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.adapters.orm.task_parent_repository import (
    create_join_continuation_if_ready,
    reconcile_completed_continuation_parents,
    wait_for_child_tasks,
)
from agent.domain.agent_task import AgentTaskKind


def test_process_termination_after_claim_is_recovered_by_another_worker(tmp_path: Path) -> None:
    database = str(tmp_path / "process-recovery.sqlite")
    run, created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="process-recovery",
        prompt="恢复测试",
        db_name=database,
    )
    assert created
    task, _ = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        idempotency_key="recover-me",
        input_payload={"objective": "恢复测试"},
        db_name=database,
    )
    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_CLAIM, database, str(task["task_uid"])],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
    )

    assert crashed.returncode == 9
    assert reclaim_expired_task_attempts(
        now=datetime.now(UTC) + timedelta(seconds=2), db_name=database
    ) == [task["task_uid"]]
    recovered = claim_task_by_uid(
        task_uid=str(task["task_uid"]),
        worker_id="recovery-worker",
        db_name=database,
    )
    assert recovered is not None
    assert recovered["current_attempt_uid"]


_CRASH_AFTER_CLAIM = """
import os
import sys
from agent.adapters.orm.task_attempt_repository import claim_task_by_uid, mark_task_running

database, task_uid = sys.argv[1:]
task = claim_task_by_uid(task_uid=task_uid, worker_id='crashed-worker', lease_seconds=1, db_name=database)
assert task is not None
assert mark_task_running(task_uid=task_uid, attempt_uid=task['current_attempt_uid'], db_name=database)
os._exit(9)
"""


def test_continuation_claim_crash_recovers_without_duplicate_parent_completion(tmp_path: Path) -> None:
    database = str(tmp_path / "continuation-recovery.sqlite")
    run, leader, _created = create_leader_run(
        project_uid="project-1", session_uid="session-1", user_uuid="user-1",
        client_request_id="continuation-recovery", prompt="Compare",
        input_payload={"prompt": "Compare"}, db_name=database,
    )
    child, _created = create_agent_task(
        run_uid=str(run["run_uid"]), parent_task_uid=str(leader["task_uid"]), kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher", idempotency_key="continuation-child", input_payload={"tool_call_id": "call-1"}, db_name=database,
    )
    leader_attempt = claim_task_by_uid(task_uid=str(leader["task_uid"]), worker_id="leader", db_name=database)
    assert leader_attempt is not None
    assert mark_task_running(task_uid=str(leader["task_uid"]), attempt_uid=str(leader_attempt["current_attempt_uid"]), db_name=database)
    assert wait_for_child_tasks(task_uid=str(leader["task_uid"]), attempt_uid=str(leader_attempt["current_attempt_uid"]), db_name=database)
    child_attempt = claim_task_by_uid(task_uid=str(child["task_uid"]), worker_id="child", db_name=database)
    assert child_attempt is not None
    assert complete_task_attempt(task_uid=str(child["task_uid"]), attempt_uid=str(child_attempt["current_attempt_uid"]), result={"summary": "Evidence"}, db_name=database)
    continuation, created = create_join_continuation_if_ready(child_task_uid=str(child["task_uid"]), db_name=database)
    assert created and continuation is not None

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_CLAIM, database, str(continuation["task_uid"])],
        cwd=Path(__file__).resolve().parents[2], check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
    )
    assert crashed.returncode == 9
    assert reclaim_expired_task_attempts(now=datetime.now(UTC) + timedelta(seconds=2), db_name=database) == [continuation["task_uid"]]
    recovered = claim_task_by_uid(task_uid=str(continuation["task_uid"]), worker_id="recovery", db_name=database)
    assert recovered is not None
    assert complete_task_attempt(task_uid=str(continuation["task_uid"]), attempt_uid=str(recovered["current_attempt_uid"]), result={"summary": "Merged"}, db_name=database)
    assert reconcile_completed_continuation_parents(db_name=database) == [leader["task_uid"]]
    assert reconcile_completed_continuation_parents(db_name=database) == []
