"""Track the source event sequence on each V2 run-item projection."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision = "20260815_09"
down_revision = "20260815_08"
branch_labels = None
depends_on = None

_BACKFILL = (
    "UPDATE agent_run_items SET last_sequence = COALESCE(("
    "SELECT MAX(events.sequence) FROM agent_run_events AS events "
    "WHERE events.run_uid = agent_run_items.run_uid AND events.item_uid = agent_run_items.item_uid"
    "), 0)"
)


def _ensure_event_columns(bind: Connection) -> None:
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_run_events")}
    if "schema_version" not in columns:
        op.add_column(
            "agent_run_events",
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        )
    if "item_uid" not in columns:
        op.add_column("agent_run_events", sa.Column("item_uid", sa.String()))
    if "task_uid" not in columns:
        op.add_column("agent_run_events", sa.Column("task_uid", sa.String()))


def upgrade() -> None:
    bind = op.get_bind()
    # Legacy databases carry agent_run_events tables created before Alembic
    # ownership, so the backfill below cannot assume the item_uid column exists
    # yet (migration 10 repeats this check as a defensive safety net).
    _ensure_event_columns(bind)
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_run_items")}
    if "last_sequence" not in columns:
        op.add_column(
            "agent_run_items",
            sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        )
    # The backfill is idempotent, so it must also run for databases where the
    # column already exists: the SQLite driver commits DDL before the failing
    # statement of an earlier attempt, leaving last_sequence behind at 0.
    bind.execute(sa.text(_BACKFILL))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_run_items")}
    if "last_sequence" in columns:
        op.drop_column("agent_run_items", "last_sequence")
