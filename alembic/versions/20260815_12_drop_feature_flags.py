"""Drop the agent_feature_flags table.

Revision ID: 20260815_12
Revises: 20260815_11
Create Date: 2026-08-15

Maintainer decision (2026-08-15): the DURABLE_AGENT_TASKS_ENABLED cohort flag
was removed; durable delegation is the only runtime path and is always on.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260815_12"
down_revision = "20260815_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_feature_flags" in tables:
        op.drop_index("idx_agent_feature_flags_lookup", table_name="agent_feature_flags")
        op.drop_table("agent_feature_flags")


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_feature_flags" not in tables:
        op.create_table(
            "agent_feature_flags",
            sa.Column("flag_name", sa.String(), primary_key=True),
            sa.Column("scope_type", sa.String(), primary_key=True),
            sa.Column("scope_id", sa.String(), primary_key=True),
            sa.Column("enabled", sa.String(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )
        op.create_index(
            "idx_agent_feature_flags_lookup",
            "agent_feature_flags",
            ["flag_name", "scope_type", "scope_id"],
        )
