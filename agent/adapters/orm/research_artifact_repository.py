"""Persistence for evidence-backed research artifacts and their task provenance."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, insert, select
from sqlalchemy.exc import IntegrityError

from ...domain.agent_task import AgentTaskKind, AgentTaskStatus, EvidencePacket
from .database import begin_runtime_write, create_engine
from .models import agent_runs, agent_tasks, research_artifacts
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
                select(agent_runs.c.project_uid, agent_runs.c.session_uid, agent_tasks.c.run_uid)
                .join(agent_runs, agent_runs.c.run_uid == agent_tasks.c.run_uid)
                .where(agent_tasks.c.task_uid == task_uid)
            ).first()
            if scope is None:
                raise LookupError("Task not found")
            timestamp = _timestamp()
            artifact_uid = f"artifact_{uuid.uuid4().hex}"
            connection.execute(
                insert(research_artifacts).values(
                    artifact_uid=artifact_uid,
                    project_uid=str(scope._mapping["project_uid"]),
                    session_uid=str(scope._mapping["session_uid"]),
                    run_uid=str(scope._mapping["run_uid"]),
                    task_uid=task_uid,
                    artifact_type=normalized_type,
                    content_json=json.dumps(content, ensure_ascii=False),
                    evidence_refs_json=json.dumps(sorted(set(evidence_refs)), ensure_ascii=False),
                    created_at=timestamp,
                    updated_at=timestamp,
                )
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
                .join(agent_runs, agent_runs.c.run_uid == research_artifacts.c.run_uid)
                .where(
                    and_(
                        research_artifacts.c.project_uid == project_uid,
                        research_artifacts.c.session_uid == session_uid,
                        agent_runs.c.uuid == user_uuid,
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
    "create_research_artifact",
    "list_research_artifacts",
    "reconcile_evidence_packet_artifacts",
]
