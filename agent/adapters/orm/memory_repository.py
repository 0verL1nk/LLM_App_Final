"""SQLAlchemy repository for governed L2-L4 context memory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import and_, delete, select, update

from .database import begin_runtime_write, create_engine
from .models import context_memory_items, session_context_summaries

MemoryLevel = Literal["L3", "L4"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_memory_items(
    *, uuid: str, project_uid: str, level: MemoryLevel, limit: int = 100, db_name: str = "./database.sqlite"
) -> list[dict[str, Any]]:
    conditions = [context_memory_items.c.uuid == uuid, context_memory_items.c.memory_level == level]
    if level == "L3":
        conditions.append(context_memory_items.c.project_uid == project_uid)
    else:
        conditions.append(context_memory_items.c.project_uid == "")
    with create_engine(db_name).connect() as connection:
        rows = connection.execute(select(context_memory_items).where(and_(*conditions)).order_by(context_memory_items.c.updated_at.desc()).limit(max(1, limit))).mappings()
        return [dict(row) for row in rows]


def upsert_memory_item(
    *, uuid: str, project_uid: str, level: MemoryLevel, memory_type: str, content: str,
    title: str = "", session_uid: str = "", source_run_uid: str = "", expires_at: str = "", db_name: str = "./database.sqlite"
) -> str:
    normalized = content.strip()
    if not normalized:
        raise ValueError("Memory content is required")
    scoped_project = project_uid if level == "L3" else ""
    now = _now()
    engine = create_engine(db_name)
    with begin_runtime_write(engine) as connection:
        existing = connection.execute(select(context_memory_items.c.memory_uid).where(and_(
            context_memory_items.c.uuid == uuid, context_memory_items.c.project_uid == scoped_project,
            context_memory_items.c.memory_level == level, context_memory_items.c.memory_type == memory_type,
            context_memory_items.c.content == normalized,
        ))).scalar_one_or_none()
        if existing:
            connection.execute(update(context_memory_items).where(context_memory_items.c.memory_uid == existing).values(
                title=title, session_uid=session_uid, source_run_uid=source_run_uid, expires_at=expires_at, updated_at=now,
            ))
            return str(existing)
        memory_uid = uuid4().hex
        connection.execute(context_memory_items.insert().values(
            memory_uid=memory_uid, uuid=uuid, project_uid=scoped_project, session_uid=session_uid,
            memory_level=level, memory_type=memory_type, title=title, content=normalized,
            source_run_uid=source_run_uid, version=1, expires_at=expires_at, created_at=now, updated_at=now,
        ))
        return memory_uid


def delete_memory_item(*, memory_uid: str, uuid: str, project_uid: str, level: MemoryLevel, db_name: str = "./database.sqlite") -> bool:
    scoped_project = project_uid if level == "L3" else ""
    with begin_runtime_write(create_engine(db_name)) as connection:
        result = connection.execute(delete(context_memory_items).where(and_(
            context_memory_items.c.memory_uid == memory_uid, context_memory_items.c.uuid == uuid,
            context_memory_items.c.project_uid == scoped_project, context_memory_items.c.memory_level == level,
        )))
        return result.rowcount == 1


def update_memory_item(
    *, memory_uid: str, uuid: str, project_uid: str, level: MemoryLevel,
    title: str, content: str, db_name: str = "./database.sqlite"
) -> bool:
    """Update an owned L3/L4 entry and advance its explicit version."""
    normalized = content.strip()
    if not normalized:
        raise ValueError("Memory content is required")
    scoped_project = project_uid if level == "L3" else ""
    with begin_runtime_write(create_engine(db_name)) as connection:
        result = connection.execute(update(context_memory_items).where(and_(
            context_memory_items.c.memory_uid == memory_uid, context_memory_items.c.uuid == uuid,
            context_memory_items.c.project_uid == scoped_project, context_memory_items.c.memory_level == level,
        )).values(title=title.strip(), content=normalized, version=context_memory_items.c.version + 1, updated_at=_now()))
        return result.rowcount == 1


def get_session_summary(*, uuid: str, project_uid: str, session_uid: str, db_name: str = "./database.sqlite") -> dict[str, Any] | None:
    with create_engine(db_name).connect() as connection:
        row = connection.execute(select(session_context_summaries).where(and_(
            session_context_summaries.c.uuid == uuid, session_context_summaries.c.project_uid == project_uid,
            session_context_summaries.c.session_uid == session_uid,
        ))).mappings().first()
        return dict(row) if row else None


__all__ = ["delete_memory_item", "get_session_summary", "list_memory_items", "update_memory_item", "upsert_memory_item"]
