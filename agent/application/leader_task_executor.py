"""Worker entry point for top-level research leader tasks."""

from __future__ import annotations

import os
import socket
from typing import Any

from ..adapters.orm.research_artifact_repository import create_research_artifact
from ..adapters.orm.task_query_repository import get_agent_task_run_context
from .run_execution import execute_research_continuation, execute_research_run
from .task_dispatcher import LeaseTaskWorker, TaskExecutorRegistry


def execute_leader_task(*, task_uid: str, db_name: str = "./database.sqlite") -> None:
    """Deliver one leader task under a database lease.

    Queue transports may redeliver this function on another instance. The task
    repository, rather than the transport, decides whether this process owns it.
    """
    worker = LeaseTaskWorker(
        worker_id=_worker_id(),
        db_name=db_name,
        executor=TaskExecutorRegistry(kind_executors={"leader": execute_leader_task_payload}),
    )
    worker.run_task(task_uid)


def execute_leader_task_payload(task: dict[str, Any]) -> dict[str, Any]:
    """Run the user interaction represented by a leased leader task."""
    task_input = task.get("input") if isinstance(task.get("input"), dict) else {}
    required = ("project_uid", "session_uid", "user_uuid", "prompt")
    if any(not str(task_input.get(field) or "").strip() for field in required):
        raise ValueError("Leader task input is incomplete")
    execution = execute_research_run(
        run_uid=str(task["run_uid"]),
        project_uid=str(task_input["project_uid"]),
        session_uid=str(task_input["session_uid"]),
        user_uuid=str(task_input["user_uuid"]),
        prompt=str(task_input["prompt"]),
        leader_task_uid=str(task["task_uid"]),
        steering_initial_delivery=bool(task_input.get("steering_initial_delivery")),
        resolved_mode=str(task_input.get("resolved_mode") or "agent_teams"),
    )
    execution_result = execution if isinstance(execution, dict) else {}
    return {
        "summary": "正在等待子研究任务" if execution_result.get("waiting_children") else "研究主任务已完成",
        "waiting_children": bool(execution_result.get("waiting_children")),
    }


def execute_continuation_task_payload(
    task: dict[str, Any], *, db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    """Resume the waiting parent Leader from validated child packets."""
    task_uid = str(task.get("task_uid") or "").strip()
    context = get_agent_task_run_context(task_uid=task_uid, db_name=db_name)
    if context is None:
        raise LookupError("Continuation task not found")
    task_input = context.get("input") if isinstance(context.get("input"), dict) else {}
    parent_task_uid = str(task_input.get("parent_task_uid") or "").strip()
    tool_results = task_input.get("tool_results")
    if not parent_task_uid or not isinstance(tool_results, list):
        raise ValueError("Continuation task input is incomplete")
    evidence_merge = task_input.get("evidence_merge") if isinstance(task_input.get("evidence_merge"), dict) else None
    if evidence_merge is not None:
        create_research_artifact(
            task_uid=task_uid,
            artifact_type="evidence_merge",
            content=evidence_merge,
            evidence_refs=[str(item) for item in evidence_merge.get("evidence_refs", []) if str(item)],
            db_name=db_name,
        )
    return execute_research_continuation(
        continuation_task_uid=task_uid,
        run_uid=str(context["run_uid"]),
        project_uid=str(context["project_uid"]),
        session_uid=str(context["session_uid"]),
        user_uuid=str(context["user_uuid"]),
        parent_task_uid=parent_task_uid,
        tool_results=[item for item in tool_results if isinstance(item, dict)],
        evidence_merge=evidence_merge,
    )


def _worker_id() -> str:
    """Return an operationally useful, process-scoped worker identity."""
    configured = os.getenv("PAPERSAGE_WORKER_ID", "").strip()
    if configured:
        return configured
    return f"{socket.gethostname()}:{os.getpid()}"


__all__ = ["execute_continuation_task_payload", "execute_leader_task", "execute_leader_task_payload"]
