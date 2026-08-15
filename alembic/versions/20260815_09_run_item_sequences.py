"""Track the source event sequence on each V2 run-item projection."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260815_09"
down_revision = "20260815_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_run_items")}
    if "last_sequence" not in columns:
        op.add_column("agent_run_items", sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"))
        bind.execute(
            sa.text(
                "UPDATE agent_run_items SET last_sequence = COALESCE(("
                "SELECT MAX(events.sequence) FROM agent_run_events AS events "
                "WHERE events.run_uid = agent_run_items.run_uid AND events.item_uid = agent_run_items.item_uid"
                "), 0)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_run_items")}
    if "last_sequence" in columns:
        op.drop_column("agent_run_items", "last_sequence")
