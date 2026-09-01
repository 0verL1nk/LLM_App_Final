"""SQLAlchemy repository for the research feedback loop tables."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select

from ...feedback.rules import (
    FINDING_MIN_REPEATS,
    FINDING_WINDOW_DAYS,
    event_idempotency_key,
)
from .database import begin_runtime_write, create_engine
from .models import (
    agent_runs,
    evidence_clicks,
    feedback_analysis_tasks,
    feedback_events,
)
from .runtime_schema import ensure_runtime_schema

# 认领租约：processing 状态超过该时长视为僵死，可被重新认领（与 memory_events 一致）。
ANALYSIS_LEASE_STALE_MINUTES = 15


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_mapping(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def enqueue_feedback_analysis_task(
    *,
    run_uid: str,
    user_uuid: str,
    project_uid: str,
    session_uid: str,
    citation_audit: str = "",
    retrieved_evidence_count: int = 0,
    evidence_doc_uids: list[str] | None = None,
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Create the durable per-run analysis task; idempotent on run_uid."""
    ensure_runtime_schema(db_name)
    now = _now()
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            existing = connection.execute(
                select(feedback_analysis_tasks).where(feedback_analysis_tasks.c.run_uid == run_uid)
            ).first()
            if existing is not None:
                return _row_mapping(existing), False
            task_uid = f"fbtask_{uuid.uuid4().hex}"
            connection.execute(
                feedback_analysis_tasks.insert().values(
                    task_uid=task_uid,
                    run_uid=run_uid,
                    user_uuid=user_uuid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    citation_audit=str(citation_audit or ""),
                    retrieved_evidence_count=max(0, int(retrieved_evidence_count or 0)),
                    evidence_doc_uids_json=json.dumps(
                        sorted({str(item) for item in evidence_doc_uids or [] if str(item)}),
                        ensure_ascii=False,
                    ),
                    status="pending",
                    error_message="",
                    created_at=now,
                    updated_at=now,
                )
            )
            row = connection.execute(
                select(feedback_analysis_tasks).where(
                    feedback_analysis_tasks.c.task_uid == task_uid
                )
            ).one()
            return _row_mapping(row), True
    finally:
        engine.dispose()


def claim_feedback_analysis_task(*, task_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Atomically claim a pending/failed (or stale-processing) task for the worker."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            stale_before = (
                datetime.now(UTC) - timedelta(minutes=ANALYSIS_LEASE_STALE_MINUTES)
            ).isoformat()
            claimed = connection.execute(
                feedback_analysis_tasks.update()
                .where(
                    and_(
                        feedback_analysis_tasks.c.task_uid == task_uid,
                        (feedback_analysis_tasks.c.status.in_(("pending", "failed")))
                        | (
                            (feedback_analysis_tasks.c.status == "processing")
                            & (feedback_analysis_tasks.c.updated_at < stale_before)
                        ),
                    )
                )
                .values(status="processing", error_message="", updated_at=_now())
                .returning(*feedback_analysis_tasks.c)
            ).first()
            return _row_mapping(claimed) if claimed is not None else None
    finally:
        engine.dispose()


def complete_feedback_analysis_task(
    *, task_uid: str, status: str = "completed", error_message: str = "", db_name: str = "./database.sqlite"
) -> None:
    """Mark a claimed task terminal; failed tasks keep their error for review."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            connection.execute(
                feedback_analysis_tasks.update()
                .where(feedback_analysis_tasks.c.task_uid == task_uid)
                .values(
                    status=str(status),
                    error_message=str(error_message or "")[:1000],
                    updated_at=_now(),
                )
            )
    finally:
        engine.dispose()


def get_feedback_run_row(*, run_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read the run row feeding signal evaluation (prompt, modes, timestamps)."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(agent_runs).where(agent_runs.c.run_uid == run_uid)
            ).first()
            return _row_mapping(row) if row is not None else None
    finally:
        engine.dispose()


def get_previous_session_run(*, run_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read the immediately preceding run of the same session, if any."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            current = connection.execute(
                select(
                    agent_runs.c.uuid,
                    agent_runs.c.project_uid,
                    agent_runs.c.session_uid,
                    agent_runs.c.created_at,
                ).where(agent_runs.c.run_uid == run_uid)
            ).first()
            if current is None:
                return None
            row = connection.execute(
                select(agent_runs)
                .where(
                    and_(
                        agent_runs.c.uuid == current.uuid,
                        agent_runs.c.project_uid == current.project_uid,
                        agent_runs.c.session_uid == current.session_uid,
                        agent_runs.c.run_uid != run_uid,
                        agent_runs.c.created_at < current.created_at,
                    )
                )
                .order_by(desc(agent_runs.c.created_at))
                .limit(1)
            ).first()
            return _row_mapping(row) if row is not None else None
    finally:
        engine.dispose()


def list_run_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Read every persisted steering input of the run in submission order."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            from .models import steering_inputs

            rows = connection.execute(
                select(
                    steering_inputs.c.input_uid,
                    steering_inputs.c.text,
                    steering_inputs.c.created_at,
                )
                .where(steering_inputs.c.run_uid == run_uid)
                .order_by(steering_inputs.c.created_at.asc())
            ).all()
            return [_row_mapping(row) for row in rows]
    finally:
        engine.dispose()


def record_feedback_event(
    *,
    user_uuid: str,
    project_uid: str,
    session_uid: str,
    run_uid: str,
    signal_type: str,
    prompt_digest: str,
    trigger_digest: str,
    doc_uid: str = "",
    payload: dict[str, Any] | None = None,
    db_name: str = "./database.sqlite",
) -> tuple[str, bool]:
    """Insert one signal event, deduplicated by its idempotency key."""
    ensure_runtime_schema(db_name)
    event_uid = event_idempotency_key(
        user_uuid=user_uuid,
        run_uid=run_uid,
        signal_type=signal_type,
        trigger_digest=trigger_digest,
    )
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            existing = connection.execute(
                select(feedback_events.c.event_uid).where(
                    feedback_events.c.event_uid == event_uid
                )
            ).first()
            if existing is not None:
                return str(existing[0]), False
            connection.execute(
                feedback_events.insert().values(
                    event_uid=event_uid,
                    user_uuid=user_uuid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    run_uid=run_uid,
                    signal_type=str(signal_type),
                    prompt_digest=str(prompt_digest),
                    doc_uid=str(doc_uid or ""),
                    payload_json=json.dumps(payload or {}, ensure_ascii=False),
                    created_at=_now(),
                )
            )
            return event_uid, True
    finally:
        engine.dispose()


def record_evidence_click(
    *,
    run_uid: str,
    user_uuid: str,
    evidence_ref: str,
    item_uid: str = "",
    db_name: str = "./database.sqlite",
) -> int:
    """Persist one evidence click telemetry row for an owned run."""
    normalized_ref = str(evidence_ref or "").strip()
    if not normalized_ref:
        raise ValueError("evidence_ref is required")
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            run = connection.execute(
                select(agent_runs.c.project_uid).where(
                    and_(agent_runs.c.run_uid == run_uid, agent_runs.c.uuid == user_uuid)
                )
            ).first()
            if run is None:
                raise LookupError("Run not found for this user")
            result = connection.execute(
                evidence_clicks.insert().values(
                    run_uid=run_uid,
                    user_uuid=user_uuid,
                    project_uid=str(run[0]),
                    evidence_ref=normalized_ref,
                    item_uid=str(item_uid or ""),
                    created_at=_now(),
                )
            )
            return int(result.inserted_primary_key[0])
    finally:
        engine.dispose()


def finding_id_for(*, project_uid: str, signal_type: str, doc_uid: str) -> str:
    """Deterministic id for one aggregation bucket (query-time materialization)."""
    digest = hashlib.sha256(
        f"{project_uid}\0{signal_type}\0{doc_uid}".encode("utf-8")
    ).hexdigest()
    return f"fb_{digest[:16]}"


def aggregate_feedback_findings(
    *,
    project_uid: str | None = None,
    min_repeats: int = FINDING_MIN_REPEATS,
    window_days: int = FINDING_WINDOW_DAYS,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    """Aggregate events into findings: GROUP BY signal/doc bucket within the window."""
    ensure_runtime_schema(db_name)
    window_start = (datetime.now(UTC) - timedelta(days=max(1, window_days))).isoformat()
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            conditions = [feedback_events.c.created_at >= window_start]
            if project_uid:
                conditions.append(feedback_events.c.project_uid == project_uid)
            buckets = connection.execute(
                select(
                    feedback_events.c.project_uid,
                    feedback_events.c.signal_type,
                    feedback_events.c.doc_uid,
                    func.count().label("repeat_count"),
                    func.min(feedback_events.c.created_at).label("first_seen_at"),
                    func.max(feedback_events.c.created_at).label("last_seen_at"),
                )
                .where(and_(*conditions))
                .group_by(
                    feedback_events.c.project_uid,
                    feedback_events.c.signal_type,
                    feedback_events.c.doc_uid,
                )
                .having(func.count() >= max(1, min_repeats))
                .order_by(desc(func.max(feedback_events.c.created_at)))
            ).all()
            findings: list[dict[str, Any]] = []
            for bucket in buckets:
                detail = _bucket_detail(
                    connection,
                    project_uid=str(bucket.project_uid),
                    signal_type=str(bucket.signal_type),
                    doc_uid=str(bucket.doc_uid or ""),
                )
                if detail is None:
                    continue
                findings.append(
                    {
                        "finding_id": finding_id_for(
                            project_uid=str(bucket.project_uid),
                            signal_type=str(bucket.signal_type),
                            doc_uid=str(bucket.doc_uid or ""),
                        ),
                        "project_uid": str(bucket.project_uid),
                        "signal_type": str(bucket.signal_type),
                        "doc_uid": str(bucket.doc_uid or ""),
                        "repeat_count": int(bucket.repeat_count),
                        "first_seen_at": str(bucket.first_seen_at),
                        "last_seen_at": str(bucket.last_seen_at),
                        "latest_prompt_preview": detail["latest_prompt_preview"],
                        "latest_prompt_digest": detail["latest_prompt_digest"],
                        "latest_run_uid": detail["latest_run_uid"],
                        "related_doc_uids": detail["related_doc_uids"],
                    }
                )
            return findings
    finally:
        engine.dispose()


def find_finding_by_id(*, finding_id: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Resolve a deterministic finding id to its bucket without window filters."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            buckets = connection.execute(
                select(
                    feedback_events.c.project_uid,
                    feedback_events.c.signal_type,
                    feedback_events.c.doc_uid,
                    func.count().label("repeat_count"),
                ).group_by(
                    feedback_events.c.project_uid,
                    feedback_events.c.signal_type,
                    feedback_events.c.doc_uid,
                )
            ).all()
            for bucket in buckets:
                if (
                    finding_id_for(
                        project_uid=str(bucket.project_uid),
                        signal_type=str(bucket.signal_type),
                        doc_uid=str(bucket.doc_uid or ""),
                    )
                    == finding_id
                ):
                    return {
                        "finding_id": finding_id,
                        "project_uid": str(bucket.project_uid),
                        "signal_type": str(bucket.signal_type),
                        "doc_uid": str(bucket.doc_uid or ""),
                        "repeat_count": int(bucket.repeat_count),
                    }
            return None
    finally:
        engine.dispose()


def latest_event_for_finding(
    *, project_uid: str, signal_type: str, doc_uid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any] | None:
    """Read the newest event of one bucket regardless of window (export path)."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            return _bucket_detail(
                connection, project_uid=project_uid, signal_type=signal_type, doc_uid=doc_uid
            )
    finally:
        engine.dispose()


def _bucket_detail(
    connection: Any, *, project_uid: str, signal_type: str, doc_uid: str
) -> dict[str, Any] | None:
    rows = connection.execute(
        select(feedback_events)
        .where(
            and_(
                feedback_events.c.project_uid == project_uid,
                feedback_events.c.signal_type == signal_type,
                feedback_events.c.doc_uid == doc_uid,
            )
        )
        .order_by(desc(feedback_events.c.created_at))
        .limit(50)
    ).all()
    if not rows:
        return None
    latest = _row_mapping(rows[0])
    latest_payload = _load_payload(str(latest.get("payload_json") or "{}"))
    related: set[str] = set()
    for row in rows:
        for item in _load_payload(str(row._mapping["payload_json"] or "{}")).get(
            "doc_uids", []
        ):
            if isinstance(item, str) and item:
                related.add(item)
    preview = str(
        latest_payload.get("prompt_preview")
        or latest_payload.get("previous_prompt_preview")
        or ""
    )
    return {
        "latest_prompt_preview": preview,
        "latest_prompt_digest": str(latest.get("prompt_digest") or ""),
        "latest_run_uid": str(latest.get("run_uid") or ""),
        "related_doc_uids": sorted(related),
    }


def _load_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "ANALYSIS_LEASE_STALE_MINUTES",
    "aggregate_feedback_findings",
    "claim_feedback_analysis_task",
    "complete_feedback_analysis_task",
    "enqueue_feedback_analysis_task",
    "finding_id_for",
    "find_finding_by_id",
    "get_feedback_run_row",
    "get_previous_session_run",
    "latest_event_for_finding",
    "list_run_steering_inputs",
    "record_evidence_click",
    "record_feedback_event",
]
