"""SQLAlchemy Core persistence for task submission and durable outbox delivery."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.engine import Connection

from ...domain.agent_task import AgentTaskKind, AgentTaskStatus, normalize_task_kind
from .database import begin_runtime_write, create_engine
from .models import agent_run_events, agent_runs, agent_task_outbox, agent_tasks
from .runtime_schema import ensure_runtime_schema


def ensure_task_dispatch_schema(db_name: str = "./database.sqlite") -> None:
    """Upgrade only databases that lack runtime tables.

    Normal service startup performs migrations once. This fallback keeps direct
    repository tests usable without invoking Alembic concurrently in workers.
    """
    ensure_runtime_schema(db_name)


def create_agent_task(
    *,
    run_uid: str,
    kind: AgentTaskKind | str,
    idempotency_key: str,
    parent_task_uid: str | None = None,
    agent_role: str = "",
    input_payload: dict[str, Any] | None = None,
    continuation_epoch: int = 0,
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Persist one task and its outbox record in the same transaction."""
    ensure_task_dispatch_schema(db_name)
    normalized_kind = normalize_task_kind(kind)
    key = idempotency_key.strip()
    if not key:
        raise ValueError("Task idempotency key is required")
    task_uid = f"task_{uuid.uuid4().hex}"
    parent_task_key = parent_task_uid or ""
    created_at = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            if connection.execute(select(agent_runs.c.run_uid).where(agent_runs.c.run_uid == run_uid)).first() is None:
                raise LookupError("Run not found")
            existing = connection.execute(
                select(agent_tasks).where(
                    and_(
                        agent_tasks.c.run_uid == run_uid,
                        agent_tasks.c.parent_task_key == parent_task_key,
                        agent_tasks.c.idempotency_key == key,
                    )
                )
            ).first()
            if existing is not None:
                return _task_from_row(existing), False
            connection.execute(
                insert(agent_tasks).values(
                    task_uid=task_uid,
                    run_uid=run_uid,
                    parent_task_uid=parent_task_uid,
                    parent_task_key=parent_task_key,
                    kind=normalized_kind,
                    agent_role=agent_role.strip(),
                    status=AgentTaskStatus.QUEUED.value,
                    idempotency_key=key,
                    continuation_epoch=max(0, continuation_epoch),
                    input_json=json.dumps(input_payload or {}, ensure_ascii=False),
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            _insert_outbox(connection, task_uid=task_uid, available_at=created_at)
            row = connection.execute(select(agent_tasks).where(agent_tasks.c.task_uid == task_uid)).one()
            return _task_from_row(row), True
    finally:
        engine.dispose()


def create_leader_run(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    client_request_id: str,
    prompt: str,
    input_payload: dict[str, Any],
    requested_mode: str = "auto",
    resolved_mode: str = "react",
    route_reason: str = "legacy_default",
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Atomically create a Run, its leader task, lifecycle event, and outbox record."""
    ensure_task_dispatch_schema(db_name)
    request_id = client_request_id.strip()
    normalized_prompt = prompt.strip()
    if not request_id:
        raise ValueError("Client request ID is required")
    if not normalized_prompt:
        raise ValueError("Prompt is required")
    created_at = _now()
    run_uid = f"run_{uuid.uuid4().hex}"
    task_uid = f"task_{uuid.uuid4().hex}"
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            existing = connection.execute(
                select(agent_runs).where(
                    and_(agent_runs.c.uuid == user_uuid, agent_runs.c.client_request_id == request_id)
                )
            ).first()
            if existing is not None:
                run = _row_mapping(existing)
                task = connection.execute(
                    select(agent_tasks).where(
                        and_(
                            agent_tasks.c.run_uid == run["run_uid"],
                            agent_tasks.c.parent_task_key == "",
                            agent_tasks.c.idempotency_key == "leader",
                        )
                    )
                ).first()
                if task is None:
                    raise RuntimeError("Existing Run has no leader task")
                return run, _task_from_row(task), False
            connection.execute(
                insert(agent_runs).values(
                    run_uid=run_uid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    uuid=user_uuid,
                    client_request_id=request_id,
                    prompt=normalized_prompt,
                    status="queued",
                    error_message="",
                    requested_mode=requested_mode,
                    resolved_mode=resolved_mode,
                    route_reason=route_reason,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(agent_run_events).values(
                    event_uid=f"evt_{uuid.uuid4().hex}",
                    run_uid=run_uid,
                    sequence=1,
                    event_type="run.created",
                    timestamp=created_at,
                    payload_json=json.dumps({"status": "queued", "requested_mode": requested_mode, "resolved_mode": resolved_mode, "route_reason": route_reason}, ensure_ascii=False),
                    schema_version=2,
                )
            )
            connection.execute(
                insert(agent_tasks).values(
                    task_uid=task_uid,
                    run_uid=run_uid,
                    parent_task_key="",
                    kind=AgentTaskKind.LEADER.value,
                    agent_role="",
                    status=AgentTaskStatus.QUEUED.value,
                    idempotency_key="leader",
                    continuation_epoch=0,
                    input_json=json.dumps(input_payload, ensure_ascii=False),
                    result_json="{}",
                    error_message="",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            _insert_outbox(connection, task_uid=task_uid, available_at=created_at)
            run = connection.execute(select(agent_runs).where(agent_runs.c.run_uid == run_uid)).one()
            task = connection.execute(select(agent_tasks).where(agent_tasks.c.task_uid == task_uid)).one()
            return _row_mapping(run), _task_from_row(task), True
    finally:
        engine.dispose()


def claim_next_task_outbox(
    *,
    worker_id: str,
    task_kinds: tuple[AgentTaskKind | str, ...] = (),
    lease_seconds: float = 60.0,
    db_name: str = "./database.sqlite",
) -> dict[str, Any] | None:
    """Lease one pending delivery using a status compare-and-set transition."""
    ensure_task_dispatch_schema(db_name)
    worker = worker_id.strip()
    if not worker:
        raise ValueError("Worker ID is required")
    kinds = tuple(normalize_task_kind(kind) for kind in task_kinds)
    claimed_at = datetime.now(UTC)
    now_text = claimed_at.isoformat()
    expires_at = (claimed_at + timedelta(seconds=max(1.0, lease_seconds))).isoformat()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            filters = [
                or_(
                    and_(agent_task_outbox.c.status == "pending", agent_task_outbox.c.available_at <= now_text),
                    and_(agent_task_outbox.c.status == "publishing", agent_task_outbox.c.lease_expires_at < now_text),
                )
            ]
            if kinds:
                filters.append(agent_tasks.c.kind.in_(kinds))
            candidate = connection.execute(
                select(agent_task_outbox.c.outbox_uid)
                .join(agent_tasks, agent_tasks.c.task_uid == agent_task_outbox.c.task_uid)
                .where(and_(*filters))
                .order_by(agent_task_outbox.c.created_at, agent_task_outbox.c.outbox_uid)
                .limit(1)
            ).scalar_one_or_none()
            if candidate is None:
                return None
            claimed = connection.execute(
                update(agent_task_outbox)
                .where(
                    and_(
                        agent_task_outbox.c.outbox_uid == candidate,
                        or_(
                            and_(agent_task_outbox.c.status == "pending", agent_task_outbox.c.available_at <= now_text),
                            and_(agent_task_outbox.c.status == "publishing", agent_task_outbox.c.lease_expires_at < now_text),
                        ),
                    )
                )
                .values(status="publishing", lease_expires_at=expires_at)
                .returning(*agent_task_outbox.c)
            ).first()
            if claimed is None:
                return None
            task_kind = connection.execute(
                select(agent_tasks.c.kind).where(agent_tasks.c.task_uid == claimed._mapping["task_uid"])
            ).scalar_one()
            return _outbox_from_row(claimed, kind=str(task_kind), publisher_id=worker)
    finally:
        engine.dispose()


def mark_task_outbox_published(*, outbox_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Acknowledge one delivery after the worker attempted its addressed task."""
    ensure_task_dispatch_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            updated = connection.execute(
                update(agent_task_outbox)
                .where(and_(agent_task_outbox.c.outbox_uid == outbox_uid, agent_task_outbox.c.status == "publishing"))
                .values(status="published", published_at=_now(), lease_expires_at=None)
            )
            return updated.rowcount == 1
    finally:
        engine.dispose()


def reclaim_expired_task_outbox_claims(
    *, now: datetime | None = None, db_name: str = "./database.sqlite"
) -> list[str]:
    """Make abandoned publisher claims eligible for another worker."""
    ensure_task_dispatch_schema(db_name)
    cutoff = _now(now)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            outbox_uids = list(
                connection.execute(
                    select(agent_task_outbox.c.outbox_uid).where(
                        and_(agent_task_outbox.c.status == "publishing", agent_task_outbox.c.lease_expires_at < cutoff)
                    )
                ).scalars()
            )
            if not outbox_uids:
                return []
            connection.execute(
                update(agent_task_outbox)
                .where(agent_task_outbox.c.outbox_uid.in_(outbox_uids))
                .values(status="pending", lease_expires_at=None)
            )
            return [str(item) for item in outbox_uids]
    finally:
        engine.dispose()


def get_task_outbox(*, outbox_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read one durable delivery record for diagnostics and tests."""
    ensure_task_dispatch_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(agent_task_outbox, agent_tasks.c.kind)
                .join(agent_tasks, agent_tasks.c.task_uid == agent_task_outbox.c.task_uid)
                .where(agent_task_outbox.c.outbox_uid == outbox_uid)
            ).first()
            return _outbox_from_row(row) if row is not None else None
    finally:
        engine.dispose()


def _insert_outbox(connection: Connection, *, task_uid: str, available_at: str) -> None:
    connection.execute(
        insert(agent_task_outbox).values(
            outbox_uid=f"outbox_{uuid.uuid4().hex}",
            task_uid=task_uid,
            event_type="task.dispatch_requested",
            payload_json=json.dumps({"task_uid": task_uid}),
            status="pending",
            available_at=available_at,
            created_at=available_at,
        )
    )


def _now(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat()


def _row_mapping(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _task_from_row(row: Any) -> dict[str, Any]:
    task = _row_mapping(row)
    task["input"] = json.loads(task.pop("input_json"))
    task["result"] = json.loads(task.pop("result_json"))
    return task


def _outbox_from_row(row: Any, *, kind: str | None = None, publisher_id: str | None = None) -> dict[str, Any]:
    payload = _row_mapping(row)
    payload["payload"] = json.loads(payload.pop("payload_json"))
    if kind is not None:
        payload["kind"] = kind
    if publisher_id is not None:
        payload["publisher_id"] = publisher_id
    return payload


__all__ = [
    "claim_next_task_outbox",
    "create_agent_task",
    "create_leader_run",
    "ensure_task_dispatch_schema",
    "get_task_outbox",
    "mark_task_outbox_published",
    "reclaim_expired_task_outbox_claims",
]
