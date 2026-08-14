"""Persist requested and resolved execution modes for durable Runs."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260814_06"
down_revision = "20260812_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    if "requested_mode" not in columns:
        op.add_column("agent_runs", sa.Column("requested_mode", sa.String(), nullable=False, server_default="auto"))
    if "resolved_mode" not in columns:
        op.add_column("agent_runs", sa.Column("resolved_mode", sa.String(), nullable=False, server_default="react"))
    if "route_reason" not in columns:
        op.add_column("agent_runs", sa.Column("route_reason", sa.String(), nullable=False, server_default="legacy_default"))


def downgrade() -> None:
    op.drop_column("agent_runs", "route_reason")
    op.drop_column("agent_runs", "resolved_mode")
    op.drop_column("agent_runs", "requested_mode")
