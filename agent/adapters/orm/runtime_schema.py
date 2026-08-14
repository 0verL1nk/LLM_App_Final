"""Readiness checks for the Alembic-owned durable runtime schema."""

from __future__ import annotations

from sqlalchemy import inspect

from .database import create_engine, run_migrations

RUNTIME_TABLES = frozenset(
    {
        "agent_runs",
        "research_artifacts",
        "research_plans",
        "research_plan_steps",
        "agent_run_events",
        "agent_run_items",
        "agent_tasks",
        "agent_task_attempts",
        "agent_task_outbox",
        "agent_steering_inputs",
    }
)


def ensure_runtime_schema(db_name: str = "./database.sqlite") -> None:
    """Upgrade only an uninitialized database for direct repository callers."""
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            if RUNTIME_TABLES.issubset(inspect(connection).get_table_names()):
                return
    finally:
        engine.dispose()
    run_migrations(db_name)
