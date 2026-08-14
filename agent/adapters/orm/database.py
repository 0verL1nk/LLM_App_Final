"""Shared SQLAlchemy/Alembic database setup without implicit schema creation."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine import URL, Connection, make_url

from alembic import command
from alembic.config import Config


def build_database_url(database: str | None = None) -> str:
    """Resolve an explicit database URL, preserving the desktop SQLite default."""
    configured = database or os.getenv("PAPERSAGE_DATABASE_URL") or os.getenv("PAPERSAGE_DATABASE")
    if not configured:
        configured = "./database.sqlite"
    if "://" in configured:
        return str(make_url(configured))
    return str(URL.create("sqlite", database=Path(configured).resolve().as_posix()))


def create_engine(database: str | None = None) -> Engine:
    """Create an engine with SQLite FK and contention settings required by task leases."""
    url = build_database_url(database)
    engine = sqlalchemy_create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _configure_sqlite(connection: object, _record: object) -> None:
            cursor = connection.cursor()  # type: ignore[attr-defined]
            try:
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA busy_timeout = 5000")
            finally:
                cursor.close()
    return engine


@contextmanager
def begin_runtime_write(engine: Engine) -> Generator[Connection, None, None]:
    """Start one serialized write transaction for lease and join state changes."""
    connection = engine.connect()
    transaction = None
    try:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            transaction = connection.begin()
        yield connection
        if transaction is None:
            connection.commit()
        else:
            transaction.commit()
    except BaseException:
        if transaction is None:
            connection.rollback()
        else:
            transaction.rollback()
        raise
    finally:
        connection.close()


def run_migrations(database: str | None = None) -> None:
    """Upgrade through Alembic; schema creation is never performed implicitly."""
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", build_database_url(database))
    command.upgrade(config, "head")
