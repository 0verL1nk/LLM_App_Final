"""Add durable revisioned research-plan snapshots and step links."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260812_05"
down_revision = "20260812_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the additive plan tables used by task lifecycle transitions."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "research_plans" not in tables:
        op.create_table(
            "research_plans",
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), primary_key=True),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )
    if "research_plan_steps" not in tables:
        op.create_table(
            "research_plan_steps",
            sa.Column("run_uid", sa.String(), sa.ForeignKey("research_plans.run_uid", ondelete="CASCADE"), primary_key=True),
            sa.Column("step_id", sa.String(), primary_key=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("depends_on_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("lane", sa.String(), nullable=False),
            sa.Column("task_uid", sa.String(), sa.ForeignKey("agent_tasks.task_uid", ondelete="SET NULL")),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )
        op.create_index("idx_research_plan_steps_task", "research_plan_steps", ["task_uid"])


def downgrade() -> None:
    """Remove only the additive plan persistence tables."""
    op.drop_index("idx_research_plan_steps_task", table_name="research_plan_steps")
    op.drop_table("research_plan_steps")
    op.drop_table("research_plans")
