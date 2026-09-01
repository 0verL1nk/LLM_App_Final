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
        "agent_feature_flags",
        "feedback_analysis_tasks",
        "feedback_events",
        "agent_evidence_clicks",
    }
)

# Columns legacy databases may predate before the reconciling 20260815_10 step.
EVENT_COLUMNS = frozenset({"schema_version", "item_uid", "task_uid"})


def ensure_runtime_schema(db_name: str = "./database.sqlite") -> None:
    """Upgrade only an uninitialized database for direct repository callers."""
    engine = create_engine(db_name)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not RUNTIME_TABLES.issubset(inspector.get_table_names()):
                run_migrations(db_name)
                return
            item_columns = {column["name"] for column in inspector.get_columns("agent_run_items")}
            event_columns = {column["name"] for column in inspector.get_columns("agent_run_events")}
            drifted = "last_sequence" not in item_columns or not EVENT_COLUMNS.issubset(event_columns)
            if drifted:
                run_migrations(db_name)
    finally:
        engine.dispose()
