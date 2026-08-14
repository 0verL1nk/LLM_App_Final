"""Lease-backed local worker primitives for durable agent tasks.

This module deliberately owns no process-global queue. Deployment code can invoke
``run_once`` from a supervised worker process today, or adapt the same repository
contract to RQ/a remote queue later.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from ..adapters.orm.research_artifact_repository import create_research_artifact
from ..adapters.orm.run_repository import append_run_item_event
from ..adapters.orm.task_attempt_repository import (
    claim_next_task,
    claim_task_by_uid,
    complete_task_attempt,
    fail_or_retry_task_attempt,
    mark_task_running,
    reclaim_expired_task_attempts,
)
from ..adapters.orm.task_parent_repository import (
    complete_waiting_parent_task,
    create_join_continuation_if_ready,
    wait_for_child_tasks,
)
from ..adapters.orm.task_query_repository import get_agent_task
from ..domain.agent_task import EvidencePacket


class AgentTaskExecutor(Protocol):
    """Execute one claimed task and return its validated result payload."""

    def __call__(self, task: dict[str, Any]) -> dict[str, Any]: ...


class TaskExecutorRegistry:
    """Resolve a claimed task by persisted kind, then role for subagent work.

    Task kind is the top-level dispatch contract. ``agent_role`` only refines a
    subagent task; it cannot decide how leader, tool, or continuation tasks run.
    The worker host injects executors, so this registry has no process-global
    scheduling state.
    """

    def __init__(
        self,
        *,
        kind_executors: Mapping[str, AgentTaskExecutor],
        subagent_executors: Mapping[str, AgentTaskExecutor] | None = None,
    ) -> None:
        self._kind_executors = {
            kind.strip(): executor for kind, executor in kind_executors.items() if kind.strip()
        }
        self._subagent_executors = {
            role.strip(): executor
            for role, executor in (subagent_executors or {}).items()
            if role.strip()
        }

    @property
    def supported_kinds(self) -> tuple[str, ...]:
        """Return the persisted kinds this registry can claim and execute."""
        kinds = set(self._kind_executors)
        if self._subagent_executors:
            kinds.add("subagent")
        return tuple(sorted(kinds))

    def __call__(self, task: dict[str, Any]) -> dict[str, Any]:
        kind = str(task.get("kind") or "").strip()
        if kind == "subagent":
            role = str(task.get("agent_role") or "").strip()
            executor = self._subagent_executors.get(role)
            if executor is None:
                raise ValueError(f"No executor is registered for subagent role: {role or '<empty>'}")
            return executor(task)
        executor = self._kind_executors.get(kind)
        if executor is None:
            raise ValueError(f"No executor is registered for task kind: {kind or '<empty>'}")
        return executor(task)


@dataclass(frozen=True)
class TaskExecutionOutcome:
    """Result of one worker polling iteration."""

    task_uid: str | None
    attempt_uid: str | None
    status: str


class LeaseTaskWorker:
    """Run one durable task at a time under repository-enforced ownership."""

    def __init__(
        self,
        *,
        worker_id: str,
        executor: AgentTaskExecutor,
        lease_seconds: float = 60.0,
        max_attempts: int = 3,
        db_name: str = "./database.sqlite",
    ) -> None:
        self._worker_id = worker_id.strip()
        self._executor = executor
        self._lease_seconds = max(1.0, lease_seconds)
        self._max_attempts = max(1, max_attempts)
        self._db_name = db_name
        if not self._worker_id:
            raise ValueError("Worker ID is required")

    def run_once(self) -> TaskExecutionOutcome:
        """Claim, execute, and commit one task; failures become durable outcomes."""
        task = claim_next_task(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            db_name=self._db_name,
        )
        return self._execute_claimed_task(task)

    def run_task(self, task_uid: str) -> TaskExecutionOutcome:
        """Execute one queue-addressed task, subject to the same database lease."""
        task = claim_task_by_uid(
            task_uid=task_uid,
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            db_name=self._db_name,
        )
        return self._execute_claimed_task(task)

    def _execute_claimed_task(self, task: dict[str, Any] | None) -> TaskExecutionOutcome:
        """Complete a task selected by either polling or an addressed delivery."""
        if task is None:
            return TaskExecutionOutcome(task_uid=None, attempt_uid=None, status="idle")
        task_uid = str(task["task_uid"])
        attempt_uid = str(task["current_attempt_uid"])
        if not mark_task_running(task_uid=task_uid, attempt_uid=attempt_uid, db_name=self._db_name):
            return TaskExecutionOutcome(task_uid=task_uid, attempt_uid=attempt_uid, status="lost_lease")
        try:
            result = self._executor(task)
        except Exception as exc:
            failure_status = fail_or_retry_task_attempt(
                task_uid=task_uid,
                attempt_uid=attempt_uid,
                error_category=_error_category(exc),
                error_message=str(exc),
                max_attempts=self._max_attempts,
                db_name=self._db_name,
            )
            completed = failure_status in {"failed", "cancelled"}
            if failure_status == "retrying" and str(task.get("kind") or "") != "leader":
                self._record_task_item(
                    task,
                    status="in_progress",
                    event_type="item.delta",
                    summary="Agent 任务将自动重试",
                )
            if completed and str(task.get("kind") or "") != "leader":
                self._record_task_item(task, status="failed", event_type="item.failed", summary="Agent 任务执行失败")
            if completed and str(task.get("kind") or "") == "subagent":
                create_join_continuation_if_ready(child_task_uid=task_uid, db_name=self._db_name)
            return TaskExecutionOutcome(
                task_uid=task_uid,
                attempt_uid=attempt_uid,
                status=failure_status,
            )
        if bool(result.get("waiting_children")):
            waiting = wait_for_child_tasks(
                task_uid=task_uid,
                attempt_uid=attempt_uid,
                db_name=self._db_name,
            )
            return TaskExecutionOutcome(
                task_uid=task_uid,
                attempt_uid=attempt_uid,
                status="waiting_children" if waiting else "lost_lease",
            )
        completed = complete_task_attempt(
            task_uid=task_uid,
            attempt_uid=attempt_uid,
            result=result,
            db_name=self._db_name,
        )
        persisted = get_agent_task(task_uid=task_uid, db_name=self._db_name) if completed else None
        terminal_status = str(persisted.get("status") or "completed") if persisted else "lost_lease"
        if completed and str(task.get("kind") or "") != "leader":
            self._record_task_item(
                task,
                status="cancelled" if terminal_status == "cancelled" else "completed",
                event_type="item.cancelled" if terminal_status == "cancelled" else "item.completed",
                summary=(
                    "Agent 任务已取消"
                    if terminal_status == "cancelled"
                    else str(result.get("summary") or "Agent 任务已完成")
                ),
            )
        if completed and terminal_status == "completed":
            self._persist_research_artifact(task, result)
        if completed and str(task.get("kind") or "") == "subagent":
            create_join_continuation_if_ready(child_task_uid=task_uid, db_name=self._db_name)
        if completed and str(task.get("kind") or "") == "continuation":
            parent_task_uid = str(result.get("parent_task_uid") or "").strip()
            if parent_task_uid:
                complete_waiting_parent_task(
                    parent_task_uid=parent_task_uid,
                    continuation_task_uid=task_uid,
                    db_name=self._db_name,
                )
        return TaskExecutionOutcome(
            task_uid=task_uid,
            attempt_uid=attempt_uid,
            status=terminal_status if completed else "lost_lease",
        )

    def reconcile_expired(self) -> list[str]:
        """Requeue abandoned active tasks before accepting more work."""
        return reclaim_expired_task_attempts(db_name=self._db_name)

    def _record_task_item(
        self,
        task: dict[str, Any],
        *,
        status: str,
        event_type: str,
        summary: str,
    ) -> None:
        """Project only the lease owner's terminal result for the durable task."""
        task_uid = str(task["task_uid"])
        task_input = task.get("input") if isinstance(task.get("input"), dict) else {}
        append_run_item_event(
            run_uid=str(task["run_uid"]),
            item_uid=f"item_agent_task_{task_uid}",
            item_type="agent_task",
            task_uid=task_uid,
            status=status,
            event_type=event_type,
            payload={
                "agent": str(task.get("agent_role") or "unknown"),
                "task": str(task_input.get("objective") or "Agent 任务"),
                "summary": summary[:600],
            },
            db_name=self._db_name,
        )

    def _persist_research_artifact(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        """Persist a validated subagent packet without coupling other task kinds to research."""
        if str(task.get("kind") or "") != "subagent":
            return
        try:
            packet = EvidencePacket.model_validate(result)
            create_research_artifact(
                task_uid=str(task["task_uid"]),
                artifact_type="evidence_packet",
                content=packet.model_dump(mode="json"),
                evidence_refs=packet.evidence_refs,
                db_name=self._db_name,
            )
        except (LookupError, ValidationError, ValueError) as exc:
            logger.error("Unable to persist subagent research artifact task_uid=%s error=%s", task["task_uid"], exc)


logger = logging.getLogger(__name__)


def _error_category(exc: Exception) -> str:
    """Classify retry policy outcomes without exposing provider internals to users."""
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "network"
    name = type(exc).__name__.lower()
    if "rate" in name and "limit" in name:
        return "rate_limited"
    if "auth" in name or "permission" in name:
        return "configuration"
    return "execution_error"


def run_worker_until_idle(
    worker: LeaseTaskWorker,
    *,
    max_tasks: int,
    on_outcome: Callable[[TaskExecutionOutcome], None] | None = None,
) -> list[TaskExecutionOutcome]:
    """Bounded worker loop suitable for a process supervisor invocation."""
    outcomes: list[TaskExecutionOutcome] = []
    for _ in range(max(0, max_tasks)):
        outcome = worker.run_once()
        outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
        if outcome.status == "idle":
            break
    return outcomes


__all__ = [
    "LeaseTaskWorker",
    "TaskExecutorRegistry",
    "AgentTaskExecutor",
    "TaskExecutionOutcome",
    "run_worker_until_idle",
]
