"""Feature flag overrides for cohort-scoped durable runtime enablement."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260815_08"
down_revision = "20260814_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("idx_agent_feature_flags_lookup", table_name="agent_feature_flags")
    op.drop_table("agent_feature_flags")
