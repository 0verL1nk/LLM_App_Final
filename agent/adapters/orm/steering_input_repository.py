"""SQLAlchemy Core repository for durable user steering inputs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select, update

from ...adapters.orm.database import create_engine
from ...adapters.orm.models import agent_runs, steering_inputs
from ...adapters.orm.runtime_schema import ensure_runtime_schema
from ...domain.steering_input import SteeringInputStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_mapping(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def ensure_steering_input_tables(db_name: str = "./database.sqlite") -> None:
    """Upgrade the queue schema without using implicit ORM table creation."""
    ensure_runtime_schema(db_name)


def enqueue_steering_input(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    client_request_id: str,
    text: str,
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Append one idempotent input to the session's currently running Run."""
    ensure_steering_input_tables(db_name)
    normalized = text.strip()
    if not normalized:
        raise ValueError("Steering input is required")
    now = _now()
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            existing = connection.execute(
                select(steering_inputs).where(
                    and_(
                        steering_inputs.c.uuid == user_uuid,
                        steering_inputs.c.client_request_id == client_request_id,
                    )
                )
            ).first()
            if existing is not None:
                return _row_mapping(existing), False
            run = connection.exec_driver_sql(
                """
                SELECT run_uid FROM agent_runs
                WHERE project_uid = ? AND session_uid = ? AND uuid = ? AND status = 'running'
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_uid, session_uid, user_uuid),
            ).first()
            if run is None:
                raise LookupError("No running Run accepts steering input")
            input_uid = f"input_{uuid.uuid4().hex}"
            connection.execute(
                steering_inputs.insert().values(
                    input_uid=input_uid,
                    run_uid=str(run[0]),
                    project_uid=project_uid,
                    session_uid=session_uid,
                    uuid=user_uuid,
                    client_request_id=client_request_id,
                    text=normalized,
                    status=SteeringInputStatus.QUEUED.value,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = connection.execute(
                select(steering_inputs).where(steering_inputs.c.input_uid == input_uid)
            ).one()
            return _row_mapping(row), True
    finally:
        engine.dispose()


def claim_queued_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Atomically claim every queued input for one upcoming model call."""
    ensure_steering_input_tables(db_name)
    now = _now()
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            rows = connection.execute(
                select(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == run_uid, steering_inputs.c.status == SteeringInputStatus.QUEUED.value))
                .order_by(steering_inputs.c.created_at.asc())
            ).all()
            input_uids = [str(row.input_uid) for row in rows]
            if not input_uids:
                return []
            claimed = connection.execute(
                update(steering_inputs)
                .where(and_(steering_inputs.c.input_uid.in_(input_uids), steering_inputs.c.status == SteeringInputStatus.QUEUED.value))
                .values(status=SteeringInputStatus.DELIVERING.value, injected_at=now, updated_at=now)
                .returning(*steering_inputs.c)
            ).all()
            return sorted((_row_mapping(row) for row in claimed), key=lambda item: str(item["created_at"]))
    finally:
        engine.dispose()


def confirm_steering_inputs(*, run_uid: str, input_uids: list[str], db_name: str = "./database.sqlite") -> list[str]:
    """Confirm only inputs still owned by this model boundary."""
    if not input_uids:
        return []
    ensure_steering_input_tables(db_name)
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            updated = connection.execute(
                update(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == run_uid, steering_inputs.c.status == SteeringInputStatus.DELIVERING.value, steering_inputs.c.input_uid.in_(input_uids)))
                .values(status=SteeringInputStatus.DELIVERED.value, confirmed_at=_now(), updated_at=_now())
            )
            return input_uids if updated.rowcount == len(input_uids) else []
    finally:
        engine.dispose()


def requeue_delivering_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[str]:
    """Make unconfirmed work replayable after an interrupted model boundary."""
    ensure_steering_input_tables(db_name)
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            input_uids = list(connection.execute(
                select(steering_inputs.c.input_uid).where(and_(steering_inputs.c.run_uid == run_uid, steering_inputs.c.status == SteeringInputStatus.DELIVERING.value))
            ).scalars())
            connection.execute(
                update(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == run_uid, steering_inputs.c.status == SteeringInputStatus.DELIVERING.value))
                .values(status=SteeringInputStatus.QUEUED.value, updated_at=_now())
            )
            return [str(item) for item in input_uids]
    finally:
        engine.dispose()


def _list_by_statuses(*, run_uid: str, statuses: list[str], db_name: str) -> list[dict[str, Any]]:
    ensure_steering_input_tables(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == run_uid, steering_inputs.c.status.in_(statuses)))
                .order_by(steering_inputs.c.created_at.asc())
            ).all()
            return [_row_mapping(row) for row in rows]
    finally:
        engine.dispose()


def list_delivered_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Read confirmed inputs in user submission order for session persistence."""
    return _list_by_statuses(run_uid=run_uid, statuses=[SteeringInputStatus.DELIVERED.value], db_name=db_name)


def list_unconfirmed_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """List queued or interrupted inputs that must not disappear with a terminal Run."""
    return _list_by_statuses(run_uid=run_uid, statuses=[SteeringInputStatus.QUEUED.value, SteeringInputStatus.DELIVERING.value], db_name=db_name)


def transfer_unconfirmed_steering_inputs(*, source_run_uid: str, target_run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Move unconfirmed inputs to a queued follow-up Run in one transaction."""
    ensure_steering_input_tables(db_name)
    engine = create_engine(db_name)
    try:
        with engine.begin() as connection:
            source = connection.execute(select(agent_runs.c.status).where(agent_runs.c.run_uid == source_run_uid)).first()
            target = connection.execute(select(agent_runs.c.status).where(agent_runs.c.run_uid == target_run_uid)).first()
            if source is None or target is None:
                raise LookupError("Run not found")
            if str(source[0]) not in {"completed", "failed"}:
                raise ValueError("Source Run has not reached a terminal state")
            if str(target[0]) != "queued":
                return []
            now = _now()
            connection.execute(
                update(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == source_run_uid, steering_inputs.c.status == SteeringInputStatus.DELIVERING.value))
                .values(status=SteeringInputStatus.QUEUED.value, updated_at=now)
            )
            rows = connection.execute(
                select(steering_inputs)
                .where(and_(steering_inputs.c.run_uid == source_run_uid, steering_inputs.c.status == SteeringInputStatus.QUEUED.value))
                .order_by(steering_inputs.c.created_at.asc())
            ).all()
            input_uids = [str(row.input_uid) for row in rows]
            if not input_uids:
                return []
            connection.execute(
                update(steering_inputs).where(steering_inputs.c.input_uid.in_(input_uids)).values(run_uid=target_run_uid, updated_at=now)
            )
            moved = connection.execute(
                select(steering_inputs).where(steering_inputs.c.input_uid.in_(input_uids)).order_by(steering_inputs.c.created_at.asc())
            ).all()
            return [_row_mapping(row) for row in moved]
    finally:
        engine.dispose()


__all__ = [
    "claim_queued_steering_inputs",
    "confirm_steering_inputs",
    "enqueue_steering_input",
    "ensure_steering_input_tables",
    "list_delivered_steering_inputs",
    "list_unconfirmed_steering_inputs",
    "requeue_delivering_steering_inputs",
    "transfer_unconfirmed_steering_inputs",
]
