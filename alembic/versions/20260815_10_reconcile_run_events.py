"""Reconcile legacy agent_run_events columns predating Alembic ownership."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260815_10"
down_revision = "20260815_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
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


def downgrade() -> None:
    # No-op: these columns belong to the 20260812_03 baseline shape, so removing
    # them would corrupt databases that already had them before this repair step.
    pass
