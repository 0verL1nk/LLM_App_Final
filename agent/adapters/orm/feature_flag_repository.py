"""SQLAlchemy Core repository for durable feature flag overrides."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select

from .database import begin_runtime_write, create_engine
from .models import feature_flags
from .runtime_schema import ensure_runtime_schema

VALID_SCOPE_TYPES = ("user", "project")


def set_feature_flag(
    *,
    flag_name: str,
    scope_type: str,
    scope_id: str,
    enabled: bool,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Upsert one scoped override; ``enabled=False`` is an explicit opt-out."""
    normalized_flag = flag_name.strip()
    normalized_scope = scope_type.strip().lower()
    normalized_id = scope_id.strip()
    if not normalized_flag:
        raise ValueError("Flag name is required")
    if normalized_scope not in VALID_SCOPE_TYPES:
        raise ValueError("scope_type must be 'user' or 'project'")
    if not normalized_id:
        raise ValueError("Scope ID is required")
    timestamp = _now()
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            connection.execute(
                delete(feature_flags).where(
                    feature_flags.c.flag_name == normalized_flag,
                    feature_flags.c.scope_type == normalized_scope,
                    feature_flags.c.scope_id == normalized_id,
                )
            )
            connection.execute(
                insert(feature_flags).values(
                    flag_name=normalized_flag,
                    scope_type=normalized_scope,
                    scope_id=normalized_id,
                    enabled="true" if enabled else "false",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            return {
                "flag_name": normalized_flag,
                "scope_type": normalized_scope,
                "scope_id": normalized_id,
                "enabled": bool(enabled),
            }
    finally:
        engine.dispose()


def clear_feature_flag(
    *,
    flag_name: str,
    scope_type: str,
    scope_id: str,
    db_name: str = "./database.sqlite",
) -> bool:
    """Remove one scoped override so resolution falls back to default/env."""
    normalized_flag = flag_name.strip()
    normalized_scope = scope_type.strip().lower()
    normalized_id = scope_id.strip()
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with begin_runtime_write(engine) as connection:
            deleted = connection.execute(
                delete(feature_flags).where(
                    feature_flags.c.flag_name == normalized_flag,
                    feature_flags.c.scope_type == normalized_scope,
                    feature_flags.c.scope_id == normalized_id,
                )
            )
            return deleted.rowcount > 0
    finally:
        engine.dispose()


def read_feature_flag(
    *,
    flag_name: str,
    scope_type: str,
    scope_id: str,
    db_name: str = "./database.sqlite",
) -> bool | None:
    """Return the stored override, or ``None`` when the scope has no row."""
    normalized_flag = flag_name.strip()
    normalized_scope = scope_type.strip().lower()
    normalized_id = scope_id.strip()
    if not normalized_flag or normalized_scope not in VALID_SCOPE_TYPES or not normalized_id:
        return None
    ensure_runtime_schema(db_name)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(feature_flags.c.enabled).where(
                    feature_flags.c.flag_name == normalized_flag,
                    feature_flags.c.scope_type == normalized_scope,
                    feature_flags.c.scope_id == normalized_id,
                )
            ).first()
            return None if row is None else str(row._mapping["enabled"]).lower() == "true"
    finally:
        engine.dispose()


def list_feature_flags(*, flag_name: str | None = None, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """List overrides for audits and admin tooling, ordered by flag then scope."""
    ensure_runtime_schema(db_name)
    filters = []
    normalized_flag = (flag_name or "").strip()
    if normalized_flag:
        filters.append(feature_flags.c.flag_name == normalized_flag)
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            statement = select(feature_flags).order_by(feature_flags.c.flag_name, feature_flags.c.scope_type, feature_flags.c.scope_id)
            if filters:
                statement = statement.where(*filters)
            rows = connection.execute(statement).all()
            return [
                {
                    "flag_name": str(row._mapping["flag_name"]),
                    "scope_type": str(row._mapping["scope_type"]),
                    "scope_id": str(row._mapping["scope_id"]),
                    "enabled": str(row._mapping["enabled"]).lower() == "true",
                }
                for row in rows
            ]
    finally:
        engine.dispose()


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "VALID_SCOPE_TYPES",
    "clear_feature_flag",
    "list_feature_flags",
    "read_feature_flag",
    "set_feature_flag",
]
