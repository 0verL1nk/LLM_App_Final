"""SQLAlchemy Core repository for durable Runs and V2 event/item projections."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, insert, select, update

from ...domain.run_item import merge_item_payload, validate_item_event
from .database import begin_runtime_write, create_engine
from .models import agent_run_events, agent_run_items, agent_runs
from .runtime_schema import ensure_runtime_schema


def create_run(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    client_request_id: str,
    prompt: str,
    requested_mode: str = "auto",
    resolved_mode: str = "react",
    route_reason: str = "legacy_default",
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Create an idempotent queued Run and its lifecycle event."""
    ensure_runtime_schema(db_name)
    created_at = _now()
    run_uid = f"run_{uuid.uuid4().hex}"
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            existing = connection.execute(
                select(agent_runs).where(
                    and_(agent_runs.c.uuid == user_uuid, agent_runs.c.client_request_id == client_request_id)
                )
            ).first()
            if existing is not None:
                return _row_mapping(existing), False
            connection.execute(
                insert(agent_runs).values(
                    run_uid=run_uid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    uuid=user_uuid,
                    client_request_id=client_request_id,
                    prompt=prompt,
                    status="queued",
                    error_message="",
                    requested_mode=requested_mode,
                    resolved_mode=resolved_mode,
                    route_reason=route_reason,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            event = _append_event(
                connection,
                run_uid=run_uid,
                event_type="run.created",
                payload={"status": "queued", "requested_mode": requested_mode, "resolved_mode": resolved_mode, "route_reason": route_reason},
                schema_version=2,
                timestamp=created_at,
            )
            run = connection.execute(select(agent_runs).where(agent_runs.c.run_uid == run_uid)).one()
            return _row_mapping(run), event is not None
    finally:
        engine.dispose()


def get_run(*, run_uid: str, user_uuid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read one Run only within its owning user scope."""
    ensure_runtime_schema(db_name)
    return _read_one(db_name, select(agent_runs).where(and_(agent_runs.c.run_uid == run_uid, agent_runs.c.uuid == user_uuid)))


def list_session_runs(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    statuses: tuple[str, ...] = ("queued", "running"),
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    """List resumable Runs scoped by user, project, and session."""
    ensure_runtime_schema(db_name)
    if not statuses:
        return []
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_runs)
                .where(
                    and_(
                        agent_runs.c.uuid == user_uuid,
                        agent_runs.c.project_uid == project_uid,
                        agent_runs.c.session_uid == session_uid,
                        agent_runs.c.status.in_(statuses),
                    )
                )
                .order_by(agent_runs.c.created_at)
            ).all()
            return [_row_mapping(row) for row in rows]
    finally:
        engine.dispose()


def append_run_event(
    *, run_uid: str, event_type: str, payload: dict[str, Any], db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    """Append a legacy V1 event for historical clients."""
    return _append_public_event(run_uid=run_uid, event_type=event_type, payload=payload, schema_version=1, db_name=db_name)


def append_run_lifecycle_event(
    *, run_uid: str, event_type: str, payload: dict[str, Any], db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    """Append a V2 operational event that does not materialize a user item."""
    return _append_public_event(run_uid=run_uid, event_type=event_type, payload=payload, schema_version=2, db_name=db_name)


def append_run_item_event(
    *,
    run_uid: str,
    item_uid: str,
    item_type: str,
    status: str,
    event_type: str,
    payload: dict[str, Any],
    task_uid: str | None = None,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Append one V2 item event and update its projection in the same transaction."""
    ensure_runtime_schema(db_name)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            run = connection.execute(select(agent_runs.c.session_uid).where(agent_runs.c.run_uid == run_uid)).first()
            if run is None:
                raise LookupError("Run not found")
            existing = connection.execute(
                select(agent_run_items).where(agent_run_items.c.item_uid == item_uid)
            ).first()
            existing_status = None if existing is None else str(existing._mapping["status"])
            validated_payload = validate_item_event(
                item_uid=item_uid,
                item_type=item_type,
                status=status,
                event_type=event_type,
                payload=payload,
                existing_status=existing_status,
            )
            item_payload = {"id": item_uid, "type": item_type, "status": status, "taskId": task_uid, "payload": validated_payload}
            event = _append_event(
                connection,
                run_uid=run_uid,
                event_type=event_type,
                payload={"item": item_payload},
                schema_version=2,
                timestamp=timestamp,
                item_uid=item_uid,
                task_uid=task_uid,
            )
            event_sequence = int(event["sequence"] if isinstance(event, dict) else event._mapping["sequence"])
            existing_payload = {} if existing is None else json.loads(existing._mapping["payload_json"])
            stored_payload = json.dumps(
                merge_item_payload(existing_payload, item_type=item_type, event_type=event_type, payload=validated_payload),
                ensure_ascii=False,
                default=str,
            )
            if existing is None:
                connection.execute(
                    insert(agent_run_items).values(
                        item_uid=item_uid,
                        run_uid=run_uid,
                        task_uid=task_uid,
                        item_type=item_type,
                        status=status,
                        payload_json=stored_payload,
                        created_at=timestamp,
                        updated_at=timestamp,
                        last_sequence=event_sequence,
                    )
                )
            else:
                values: dict[str, Any] = {"status": status, "payload_json": stored_payload, "updated_at": timestamp, "last_sequence": event_sequence}
                if task_uid is not None:
                    values["task_uid"] = task_uid
                connection.execute(update(agent_run_items).where(agent_run_items.c.item_uid == item_uid).values(**values))
            connection.execute(update(agent_runs).where(agent_runs.c.run_uid == run_uid).values(updated_at=timestamp))
            return _public_event(event, run_uid=run_uid, session_uid=str(run._mapping["session_uid"]))
    finally:
        engine.dispose()


def get_run_item(*, run_uid: str, item_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read one projected Run item for replay and continuation checks."""
    row = _read_one(
        db_name,
        select(agent_run_items).where(and_(agent_run_items.c.run_uid == run_uid, agent_run_items.c.item_uid == item_uid)),
    )
    if row is None:
        return None
    return {
        "id": str(row["item_uid"]),
        "taskId": row["task_uid"],
        "type": str(row["item_type"]),
        "status": str(row["status"]),
        "payload": json.loads(row["payload_json"]),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]),
        "sequence": int(row["last_sequence"]),
    }


class _RunItemSnapshot(list):
    """Item snapshot: a plain list of projections that also answers
    ["items"] (sequence-enriched) and ["lastSequence"] for replay callers."""

    def __init__(self, items: list[dict[str, Any]], last_sequence: int) -> None:
        super().__init__({key: value for key, value in item.items() if key != "sequence"} for item in items)
        self._enriched = items
        self.last_sequence = last_sequence

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key == "items":
                return self._enriched
            if key == "lastSequence":
                return self.last_sequence
            raise KeyError(key)
        return super().__getitem__(key)


def list_run_items(
    *, run_uid: str, after_sequence: int = 0, db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    """Return the V2 item snapshot and the event-sequence replay cursor."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            last_sequence = int(
                connection.execute(
                    select(func.max(agent_run_events.c.sequence)).where(agent_run_events.c.run_uid == run_uid)
                ).scalar_one()
                or 0
            )
            rows = connection.execute(
                select(agent_run_items)
                .where(and_(agent_run_items.c.run_uid == run_uid, agent_run_items.c.last_sequence > after_sequence))
                .order_by(agent_run_items.c.last_sequence, agent_run_items.c.item_uid)
            ).all()
            items = [
                {
                    "id": str(row._mapping["item_uid"]),
                    "taskId": row._mapping["task_uid"],
                    "type": str(row._mapping["item_type"]),
                    "status": str(row._mapping["status"]),
                    "payload": json.loads(row._mapping["payload_json"]),
                    "createdAt": str(row._mapping["created_at"]),
                    "updatedAt": str(row._mapping["updated_at"]),
                    "sequence": int(row._mapping["last_sequence"]),
                }
                for row in rows
            ]
            return _RunItemSnapshot(items, last_sequence)
    finally:
        engine.dispose()


def list_run_events(*, run_uid: str, after_sequence: int = 0, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Read ordered event replay after an exclusive sequence cursor."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_run_events, agent_runs.c.session_uid)
                .join(agent_runs, agent_runs.c.run_uid == agent_run_events.c.run_uid)
                .where(and_(agent_run_events.c.run_uid == run_uid, agent_run_events.c.sequence > after_sequence))
                .order_by(agent_run_events.c.sequence)
            ).all()
            return [_public_event(row, run_uid=run_uid, session_uid=str(row._mapping["session_uid"])) for row in rows]
    finally:
        engine.dispose()


def update_run_status(*, run_uid: str, status: str, error_message: str = "", db_name: str = "./database.sqlite") -> bool:
    """Transition a queued/running Run to one terminal state."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            updated = connection.execute(
                update(agent_runs)
                .where(and_(agent_runs.c.run_uid == run_uid, agent_runs.c.status.in_(("queued", "running", "waiting_children"))))
                .values(status=status, error_message=error_message[:1000], updated_at=_now())
            )
            return updated.rowcount == 1
    finally:
        engine.dispose()


def claim_run_execution(*, run_uid: str, db_name: str = "./database.sqlite") -> bool:
    """Claim a queued Run exactly once before worker execution."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            claimed = connection.execute(
                update(agent_runs)
                .where(and_(agent_runs.c.run_uid == run_uid, agent_runs.c.status == "queued"))
                .values(status="running", updated_at=_now())
            )
            return claimed.rowcount == 1
    finally:
        engine.dispose()


def expire_stalled_runs(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    max_idle_seconds: float,
    db_name: str = "./database.sqlite",
) -> list[str]:
    """Fail scoped active Runs that stopped producing durable updates."""
    ensure_runtime_schema(db_name)
    cutoff = datetime.now(UTC).timestamp() - max(1.0, max_idle_seconds)
    candidates = list_session_runs(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        statuses=("queued", "running"),
        db_name=db_name,
    )
    expired: list[str] = []
    for run in candidates:
        try:
            updated_at = datetime.fromisoformat(str(run["updated_at"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            updated_at = 0.0
        if updated_at >= cutoff:
            continue
        run_uid = str(run["run_uid"])
        if update_run_status(run_uid=run_uid, status="failed", error_message="Run stalled", db_name=db_name):
            append_run_lifecycle_event(
                run_uid=run_uid,
                event_type="run.failed",
                payload={"message": "研究运行超时，未收到新的进展。请重试。"},
                db_name=db_name,
            )
            expired.append(run_uid)
    return expired


def _append_public_event(*, run_uid: str, event_type: str, payload: dict[str, Any], schema_version: int, db_name: str) -> dict[str, Any]:
    ensure_runtime_schema(db_name)
    timestamp = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            run = connection.execute(select(agent_runs.c.session_uid).where(agent_runs.c.run_uid == run_uid)).first()
            if run is None:
                raise LookupError("Run not found")
            event = _append_event(connection, run_uid=run_uid, event_type=event_type, payload=payload, schema_version=schema_version, timestamp=timestamp)
            connection.execute(update(agent_runs).where(agent_runs.c.run_uid == run_uid).values(updated_at=timestamp))
            return _public_event(event, run_uid=run_uid, session_uid=str(run._mapping["session_uid"]))
    finally:
        engine.dispose()


def _append_event(connection: Any, *, run_uid: str, event_type: str, payload: dict[str, Any], schema_version: int, timestamp: str, item_uid: str | None = None, task_uid: str | None = None) -> dict[str, Any]:
    sequence = int(connection.execute(select(func.coalesce(func.max(agent_run_events.c.sequence), 0) + 1).where(agent_run_events.c.run_uid == run_uid)).scalar_one())
    event_uid = f"evt_{uuid.uuid4().hex}"
    connection.execute(insert(agent_run_events).values(event_uid=event_uid, run_uid=run_uid, sequence=sequence, event_type=event_type, timestamp=timestamp, payload_json=json.dumps(payload, ensure_ascii=False, default=str), schema_version=schema_version, item_uid=item_uid, task_uid=task_uid))
    return {"event_uid": event_uid, "sequence": sequence, "event_type": event_type, "timestamp": timestamp, "payload": payload, "schema_version": schema_version}


_V2_PUBLIC_PAYLOAD_EVENT_TYPES = frozenset({"run.started", "run.completed", "run.failed", "run.cancelled"})


def _public_event(event: Any, *, run_uid: str, session_uid: str) -> dict[str, Any]:
    mapping = event if isinstance(event, dict) else event._mapping
    payload = mapping["payload"] if isinstance(mapping.get("payload"), dict) else json.loads(mapping["payload_json"])
    result: dict[str, Any] = {"version": int(mapping["schema_version"]), "eventId": str(mapping["event_uid"]), "eventType": str(mapping["event_type"]), "sequence": int(mapping["sequence"]), "timestamp": str(mapping["timestamp"]), "threadId": session_uid, "runId": run_uid, "traceId": f"trace_{run_uid.removeprefix('run_')}", "payload": payload if int(mapping["schema_version"]) == 1 or str(mapping["event_type"]) in _V2_PUBLIC_PAYLOAD_EVENT_TYPES else {}}
    if int(mapping["schema_version"]) == 2 and isinstance(payload.get("item"), dict):
        result["item"] = payload["item"]
    return result


def _project_item_payload(existing_payload: dict[str, Any], *, item_type: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if item_type in {"assistant_message", "reasoning_summary"} and event_type == "item.delta":
        return {**existing_payload, **payload, "text": str(existing_payload.get("text") or "") + str(payload.get("delta") or "")}
    if item_type == "presentation" and event_type == "item.delta":
        envelopes = list(existing_payload.get("envelopes") or [])
        if isinstance(payload.get("envelope"), dict):
            envelopes.append(payload["envelope"])
        return {**existing_payload, **payload, "envelopes": envelopes}
    return {**existing_payload, **payload}


def _read_one(db_name: str, statement: Any) -> dict[str, Any] | None:
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(statement).first()
            return _row_mapping(row) if row is not None else None
    finally:
        engine.dispose()


def _row_mapping(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["append_run_event", "append_run_item_event", "append_run_lifecycle_event", "claim_run_execution", "create_run", "expire_stalled_runs", "get_run", "list_run_events", "list_run_items", "list_session_runs", "update_run_status"]
