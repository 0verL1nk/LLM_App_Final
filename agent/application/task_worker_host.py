"""Supervised polling host for durable task-outbox delivery."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass

from ..adapters.orm.research_artifact_repository import reconcile_evidence_packet_artifacts
from ..adapters.orm.task_dispatch_repository import (
    claim_next_task_outbox,
    mark_task_outbox_published,
    reclaim_expired_task_outbox_claims,
)
from ..adapters.orm.task_parent_repository import (
    reconcile_completed_continuation_parents,
    reconcile_waiting_child_joins,
)
from ..domain.agent_task import AgentTaskKind
from ..subagent.loader import load_subagent_definitions
from .leader_task_executor import execute_continuation_task_payload, execute_leader_task_payload
from .subagent_task_executor import execute_subagent_task_payload
from .task_dispatcher import (
    AgentTaskExecutor,
    LeaseTaskWorker,
    TaskExecutionOutcome,
    TaskExecutorRegistry,
)


@dataclass(frozen=True)
class OutboxDeliveryOutcome:
    """One publisher iteration and the task execution it triggered."""

    outbox_uid: str | None
    task_outcome: TaskExecutionOutcome | None
    status: str


class TaskOutboxWorker:
    """Publish durable outbox records and execute registered durable task kinds."""

    def __init__(
        self,
        *,
        worker_id: str,
        db_name: str = "./database.sqlite",
        lease_seconds: float = 60.0,
        executor: AgentTaskExecutor | None = None,
        task_kinds: tuple[str, ...] | None = None,
    ) -> None:
        normalized_worker_id = worker_id.strip()
        if not normalized_worker_id:
            raise ValueError("Worker ID is required")
        self._worker_id = normalized_worker_id
        self._db_name = db_name
        self._lease_seconds = max(1.0, lease_seconds)
        definitions = load_subagent_definitions()
        resolved_executor = executor or TaskExecutorRegistry(
            kind_executors={
                AgentTaskKind.LEADER.value: execute_leader_task_payload,
                AgentTaskKind.CONTINUATION.value: (
                    lambda task: execute_continuation_task_payload(task, db_name=db_name)
                ),
            },
            subagent_executors={
                definition.name: (
                    lambda task, definition=definition: execute_subagent_task_payload(
                        task,
                        definition=definition,
                        db_name=db_name,
                    )
                )
                for definition in definitions
            },
        )
        if task_kinds is not None:
            self._task_kinds = task_kinds
        elif isinstance(resolved_executor, TaskExecutorRegistry):
            self._task_kinds = resolved_executor.supported_kinds
        else:
            raise ValueError("task_kinds is required when executor is not a TaskExecutorRegistry")
        self._task_worker = LeaseTaskWorker(
            worker_id=normalized_worker_id,
            db_name=db_name,
            lease_seconds=lease_seconds,
            executor=resolved_executor,
        )

    def run_once(self) -> OutboxDeliveryOutcome:
        """Recover stale publishers, deliver one registered task, then acknowledge delivery."""
        reclaim_expired_task_outbox_claims(db_name=self._db_name)
        self._task_worker.reconcile_expired()
        reconcile_waiting_child_joins(db_name=self._db_name)
        reconcile_completed_continuation_parents(db_name=self._db_name)
        reconcile_evidence_packet_artifacts(db_name=self._db_name)
        outbox = claim_next_task_outbox(
            worker_id=self._worker_id,
            task_kinds=self._task_kinds,
            lease_seconds=self._lease_seconds,
            db_name=self._db_name,
        )
        if outbox is None:
            return OutboxDeliveryOutcome(outbox_uid=None, task_outcome=None, status="idle")
        outcome = self._task_worker.run_task(str(outbox["task_uid"]))
        acknowledged = outcome.status != "lost_lease" and mark_task_outbox_published(
            outbox_uid=str(outbox["outbox_uid"]), db_name=self._db_name
        )
        return OutboxDeliveryOutcome(
            outbox_uid=str(outbox["outbox_uid"]),
            task_outcome=outcome,
            status="delivered" if acknowledged else "lost_outbox_lease",
        )

    def run_task(self, task_uid: str) -> TaskExecutionOutcome:
        """Execute an addressed local delivery through the shared task registry."""
        return self._task_worker.run_task(task_uid)


def run_task_worker_forever(
    *,
    db_name: str = "./database.sqlite",
    poll_seconds: float = 1.0,
    worker_id: str | None = None,
) -> None:
    """Run the registered durable-task worker under an external supervisor."""
    host = TaskOutboxWorker(worker_id=worker_id or _worker_id(), db_name=db_name)
    while True:
        outcome = host.run_once()
        if outcome.status == "idle":
            time.sleep(max(0.05, poll_seconds))


def execute_registered_task(*, task_uid: str, db_name: str = "./database.sqlite") -> None:
    """Deliver one locally nudged task through the same lease-backed registry."""
    host = TaskOutboxWorker(worker_id=_worker_id(), db_name=db_name)
    host.run_task(task_uid)


def _worker_id() -> str:
    configured = os.getenv("PAPERSAGE_WORKER_ID", "").strip()
    return configured or f"{socket.gethostname()}:{os.getpid()}"


__all__ = [
    "OutboxDeliveryOutcome",
    "TaskOutboxWorker",
    "execute_registered_task",
    "run_task_worker_forever",
]


if __name__ == "__main__":
    run_task_worker_forever(
        db_name=os.getenv("PAPERSAGE_DATABASE", "./database.sqlite"),
        poll_seconds=float(os.getenv("PAPERSAGE_TASK_POLL_SECONDS", "1.0")),
    )
