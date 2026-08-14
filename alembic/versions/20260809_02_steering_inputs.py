"""Create the durable steering-input queue for fresh installations."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260809_02"
down_revision = "20260809_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create only when upgrading a database that lacks the legacy table."""
    bind = op.get_bind()
    if "agent_steering_inputs" in inspect(bind).get_table_names():
        return
    op.create_table(
        "agent_steering_inputs",
        sa.Column("input_uid", sa.String(), primary_key=True),
        sa.Column("run_uid", sa.String(), nullable=False),
        sa.Column("project_uid", sa.String(), nullable=False),
        sa.Column("session_uid", sa.String(), nullable=False),
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("client_request_id", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("injected_at", sa.String()),
        sa.Column("confirmed_at", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["run_uid"], ["agent_runs.run_uid"], ondelete="CASCADE"),
        sa.UniqueConstraint("uuid", "client_request_id", name="uq_agent_steering_inputs_request"),
    )
    op.create_index(
        "idx_agent_steering_inputs_run",
        "agent_steering_inputs",
        ["run_uid", "status", "created_at"],
    )


def downgrade() -> None:
    """Drop only the queue introduced by this migration."""
    op.drop_index("idx_agent_steering_inputs_run", table_name="agent_steering_inputs")
    op.drop_table("agent_steering_inputs")
