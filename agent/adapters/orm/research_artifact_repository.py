"""Persistence for evidence-backed research artifacts and their task provenance."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from ...domain.run_item import sanitize_item_payload
from ...domain.agent_task import AgentTaskKind, AgentTaskStatus, EvidencePacket
from .database import begin_runtime_write, create_engine
from .models import agent_runs, agent_tasks, research_artifact_revisions, research_artifacts
from .runtime_schema import ensure_runtime_schema

logger = logging.getLogger(__name__)


def create_research_artifact(
    *,
    task_uid: str,
    artifact_type: str,
    content: dict[str, Any],
    evidence_refs: list[str],
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Persist one task-derived artifact, deriving scope from durable task ownership."""
    ensure_runtime_schema(db_name)
    normalized_type = artifact_type.strip().lower()
    if not normalized_type:
        raise ValueError("Artifact type is required")
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            existing = connection.execute(
                select(research_artifacts).where(research_artifacts.c.task_uid == task_uid)
            ).first()
            if existing is not None:
                return _artifact_from_row(existing), False
            scope = connection.execute(
                select(agent_runs.c.project_uid, agent_runs.c.session_uid, agent_runs.c.uuid, agent_tasks.c.run_uid)
                .join(agent_runs, agent_runs.c.run_uid == agent_tasks.c.run_uid)
                .where(agent_tasks.c.task_uid == task_uid)
            ).first()
            if scope is None:
                raise LookupError("Task not found")
            timestamp = _timestamp()
            artifact_uid = f"artifact_{uuid.uuid4().hex}"
            run_uid = str(scope._mapping["run_uid"])
            connection.execute(
                insert(research_artifacts).values(
                    artifact_uid=artifact_uid,
                    project_uid=str(scope._mapping["project_uid"]),
                    session_uid=str(scope._mapping["session_uid"]),
                    uuid=str(scope._mapping["uuid"]),
                    run_uid=run_uid,
                    task_uid=task_uid,
                    artifact_type=normalized_type,
                    content_json=json.dumps(sanitize_item_payload(content), ensure_ascii=False),
                    evidence_refs_json=json.dumps(sorted(set(evidence_refs)), ensure_ascii=False),
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            _insert_revision(
                connection,
                artifact_uid=artifact_uid,
                revision=1,
                status="accepted",
                content=content,
                evidence_refs=sorted(set(evidence_refs)),
                source_run_uid=run_uid,
                source_task_uid=task_uid,
                timestamp=timestamp,
            )
            artifact = connection.execute(
                select(research_artifacts).where(research_artifacts.c.artifact_uid == artifact_uid)
            ).one()
            return _artifact_from_row(artifact), True
    except IntegrityError:
        # A unique task artifact may have committed in another worker after the read.
        return _read_by_task(task_uid=task_uid, db_name=db_name), False
    finally:
        engine.dispose()


def list_research_artifacts(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    """List artifacts only through their owning Run's user/project/session scope."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(research_artifacts)
                .where(
                    and_(
                        research_artifacts.c.project_uid == project_uid,
                        research_artifacts.c.session_uid == session_uid,
                        research_artifacts.c.uuid == user_uuid,
                    )
                )
                .order_by(research_artifacts.c.created_at, research_artifacts.c.artifact_uid)
            ).all()
            return [_artifact_from_row(row) for row in rows]
    finally:
        engine.dispose()


def reconcile_evidence_packet_artifacts(*, db_name: str = "./database.sqlite") -> list[str]:
    """Backfill packets if a process ended after task completion but before artifact write."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(agent_tasks.c.task_uid, agent_tasks.c.result_json)
                .outerjoin(research_artifacts, research_artifacts.c.task_uid == agent_tasks.c.task_uid)
                .where(
                    and_(
                        agent_tasks.c.kind == AgentTaskKind.SUBAGENT.value,
                        agent_tasks.c.status == AgentTaskStatus.COMPLETED.value,
                        research_artifacts.c.artifact_uid.is_(None),
                    )
                )
            ).all()
    finally:
        engine.dispose()
    repaired: list[str] = []
    for row in rows:
        task_uid = str(row._mapping["task_uid"])
        try:
            packet = EvidencePacket.model_validate(json.loads(row._mapping["result_json"]))
            _artifact, created = create_research_artifact(
                task_uid=task_uid,
                artifact_type="evidence_packet",
                content=packet.model_dump(mode="json"),
                evidence_refs=packet.evidence_refs,
                db_name=db_name,
            )
            if created:
                repaired.append(task_uid)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Skipping invalid completed subagent artifact task_uid=%s error=%s", task_uid, exc)
            continue
    return repaired



def create_scoped_research_artifact(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    artifact_type: str,
    content: dict[str, Any],
    evidence_refs: list[str],
    validity_scope: str = "",
    update_policy: str = "",
    source_run_uid: str = "",
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Persist a user-scoped artifact with a proposed first revision; a supplied
    source_run_uid records which Run requested the draft without task ownership."""
    ensure_runtime_schema(db_name)
    normalized_type = artifact_type.strip().lower()
    if not normalized_type:
        raise ValueError("Artifact type is required")
    engine = create_engine(db_name)
    try:
        timestamp = _timestamp()
        artifact_uid = f"artifact_{uuid.uuid4().hex}"
        with begin_runtime_write(engine) as connection:
            connection.execute(
                insert(research_artifacts).values(
                    artifact_uid=artifact_uid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    uuid=user_uuid,
                    run_uid=source_run_uid or None,
                    task_uid=None,
                    artifact_type=normalized_type,
                    content_json=json.dumps(sanitize_item_payload(content), ensure_ascii=False),
                    evidence_refs_json=json.dumps(sorted(set(evidence_refs)), ensure_ascii=False),
                    validity_scope=validity_scope,
                    update_policy=update_policy,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            _insert_revision(
                connection,
                artifact_uid=artifact_uid,
                revision=1,
                status="proposed",
                content=content,
                evidence_refs=sorted(set(evidence_refs)),
                source_run_uid=source_run_uid,
                source_task_uid="",
                timestamp=timestamp,
            )
            artifact = connection.execute(
                select(research_artifacts).where(research_artifacts.c.artifact_uid == artifact_uid)
            ).one()
            return _artifact_from_row(artifact)
    finally:
        engine.dispose()


def get_research_artifact(*, artifact_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    """Read one artifact regardless of task or scoped ownership."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(research_artifacts).where(research_artifacts.c.artifact_uid == artifact_uid)
            ).first()
            return _artifact_from_row(row) if row is not None else None
    finally:
        engine.dispose()


def add_research_artifact_revision(
    *,
    artifact_uid: str,
    content: dict[str, Any],
    evidence_refs: list[str],
    based_on_revision_uid: str = "",
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Append a proposed revision; existing revisions are never overwritten."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        timestamp = _timestamp()
        with begin_runtime_write(engine) as connection:
            artifact = connection.execute(
                select(research_artifacts).where(research_artifacts.c.artifact_uid == artifact_uid)
            ).first()
            if artifact is None:
                raise LookupError("Artifact not found")
            next_revision = int(
                connection.execute(
                    select(func.max(research_artifact_revisions.c.revision)).where(
                        research_artifact_revisions.c.artifact_uid == artifact_uid
                    )
                ).scalar_one()
                or 0
            ) + 1
            revision_uid = f"revision_{uuid.uuid4().hex}"
            connection.execute(
                insert(research_artifact_revisions).values(
                    revision_uid=revision_uid,
                    artifact_uid=artifact_uid,
                    revision=next_revision,
                    status="proposed",
                    content_json=json.dumps(sanitize_item_payload(content), ensure_ascii=False),
                    evidence_refs_json=json.dumps(sorted(set(evidence_refs)), ensure_ascii=False),
                    source_run_uid=str(artifact._mapping["run_uid"] or ""),
                    source_task_uid=str(artifact._mapping["task_uid"] or ""),
                    based_on_revision_uid=based_on_revision_uid,
                    created_at=timestamp,
                )
            )
            connection.execute(
                update(research_artifacts)
                .where(research_artifacts.c.artifact_uid == artifact_uid)
                .values(updated_at=timestamp)
            )
            row = connection.execute(
                select(research_artifact_revisions).where(
                    research_artifact_revisions.c.revision_uid == revision_uid
                )
            ).one()
            return _revision_from_row(row)
    finally:
        engine.dispose()


def decide_research_artifact_revision(
    *,
    artifact_uid: str,
    revision_uid: str,
    decision: str,
    note: str = "",
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    """Accept or reject one proposed revision exactly once."""
    normalized = decision.strip().lower()
    if normalized not in {"accepted", "rejected"}:
        raise ValueError("decision must be 'accepted' or 'rejected'")
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        timestamp = _timestamp()
        with begin_runtime_write(engine) as connection:
            updated = connection.execute(
                update(research_artifact_revisions)
                .where(
                    and_(
                        research_artifact_revisions.c.artifact_uid == artifact_uid,
                        research_artifact_revisions.c.revision_uid == revision_uid,
                        research_artifact_revisions.c.status == "proposed",
                    )
                )
                .values(status=normalized, decision_note=note, decided_at=timestamp)
            )
            row = connection.execute(
                select(research_artifact_revisions).where(
                    research_artifact_revisions.c.revision_uid == revision_uid
                )
            ).first()
            if row is None:
                raise LookupError("Revision not found")
            if updated.rowcount != 1:
                return _revision_from_row(row), False
            if normalized == "accepted":
                connection.execute(
                    update(research_artifacts)
                    .where(research_artifacts.c.artifact_uid == artifact_uid)
                    .values(
                        content_json=row._mapping["content_json"],
                        evidence_refs_json=row._mapping["evidence_refs_json"],
                        updated_at=timestamp,
                    )
                )
            return _revision_from_row(row), True
    finally:
        engine.dispose()


def list_research_artifact_revisions(
    *, artifact_uid: str, db_name: str = "./database.sqlite"
) -> list[dict[str, Any]]:
    """Read the append-only revision history in order."""
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(research_artifact_revisions)
                .where(research_artifact_revisions.c.artifact_uid == artifact_uid)
                .order_by(research_artifact_revisions.c.revision)
            ).all()
            return [_revision_from_row(row) for row in rows]
    finally:
        engine.dispose()


def _insert_revision(
    connection: Any,
    *,
    artifact_uid: str,
    revision: int,
    status: str,
    content: dict[str, Any],
    evidence_refs: list[str],
    source_run_uid: str,
    source_task_uid: str,
    timestamp: str,
) -> None:
    connection.execute(
        insert(research_artifact_revisions).values(
            revision_uid=f"revision_{uuid.uuid4().hex}",
            artifact_uid=artifact_uid,
            revision=revision,
            status=status,
            content_json=json.dumps(sanitize_item_payload(content), ensure_ascii=False),
            evidence_refs_json=json.dumps(evidence_refs, ensure_ascii=False),
            source_run_uid=source_run_uid,
            source_task_uid=source_task_uid,
            created_at=timestamp,
        )
    )


def _revision_from_row(row: Any) -> dict[str, Any]:
    revision = dict(row._mapping)
    revision["content"] = json.loads(revision.pop("content_json"))
    revision["evidence_refs"] = json.loads(revision.pop("evidence_refs_json"))
    return revision


def _read_by_task(*, task_uid: str, db_name: str) -> dict[str, Any]:
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(research_artifacts).where(research_artifacts.c.task_uid == task_uid)
            ).one()
            return _artifact_from_row(row)
    finally:
        engine.dispose()


def _artifact_from_row(row: Any) -> dict[str, Any]:
    artifact = dict(row._mapping)
    artifact["content"] = json.loads(artifact.pop("content_json"))
    artifact["evidence_refs"] = json.loads(artifact.pop("evidence_refs_json"))
    return artifact


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "add_research_artifact_revision",
    "create_research_artifact",
    "create_scoped_research_artifact",
    "decide_research_artifact_revision",
    "get_research_artifact",
    "list_research_artifact_revisions",
    "list_research_artifacts",
    "reconcile_evidence_packet_artifacts",
]
