from pathlib import Path
from threading import Barrier, Lock, Thread

from agent.adapters.orm.task_attempt_repository import (
    claim_task_by_uid,
    complete_task_attempt,
    mark_task_running,
)
from agent.adapters.orm.task_dispatch_repository import create_agent_task, create_leader_run
from agent.adapters.orm.task_parent_repository import (
    create_join_continuation_if_ready,
    wait_for_child_tasks,
)
from agent.domain.agent_task import AgentTaskKind


def test_concurrent_join_reconciliation_creates_one_continuation(tmp_path: Path) -> None:
    database = str(tmp_path / "concurrent-join.sqlite")
    run, leader, _ = create_leader_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="concurrent-join",
        prompt="比较论文",
        input_payload={"prompt": "比较论文"},
        db_name=database,
    )
    children = [
        create_agent_task(
            run_uid=str(run["run_uid"]),
            parent_task_uid=str(leader["task_uid"]),
            kind=AgentTaskKind.SUBAGENT,
            agent_role="researcher",
            idempotency_key=f"concurrent-child-{index}",
            input_payload={"tool_call_id": f"call-{index}"},
            db_name=database,
        )[0]
        for index in range(2)
    ]
    leased_leader = claim_task_by_uid(task_uid=str(leader["task_uid"]), worker_id="leader", db_name=database)
    assert leased_leader is not None
    assert mark_task_running(task_uid=str(leader["task_uid"]), attempt_uid=str(leased_leader["current_attempt_uid"]), db_name=database)
    assert wait_for_child_tasks(task_uid=str(leader["task_uid"]), attempt_uid=str(leased_leader["current_attempt_uid"]), db_name=database)
    for index, child in enumerate(children):
        leased = claim_task_by_uid(task_uid=str(child["task_uid"]), worker_id=f"child-{index}", db_name=database)
        assert leased is not None
        assert complete_task_attempt(task_uid=str(child["task_uid"]), attempt_uid=str(leased["current_attempt_uid"]), result={"summary": str(index)}, db_name=database)

    barrier = Barrier(2)
    guard = Lock()
    outcomes: list[tuple[dict[str, object] | None, bool]] = []

    def reconcile() -> None:
        barrier.wait()
        outcome = create_join_continuation_if_ready(child_task_uid=str(children[-1]["task_uid"]), db_name=database)
        with guard:
            outcomes.append(outcome)

    threads = [Thread(target=reconcile), Thread(target=reconcile)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(1 for _continuation, created in outcomes if created) == 1
    continuation_ids = {str(continuation["task_uid"]) for continuation, _created in outcomes if continuation}
    assert len(continuation_ids) == 1
    continuation = next(continuation for continuation, _created in outcomes if continuation is not None)
    assert continuation is not None
    assert continuation["input"]["evidence_merge"]["failed_tasks"] == []
    assert continuation["input"]["evidence_merge"]["packet_summaries"] == [
        {
            "task_uid": str(child["task_uid"]),
            "role": "researcher",
            "summary": str(index),
        }
        for index, child in enumerate(children)
    ]
