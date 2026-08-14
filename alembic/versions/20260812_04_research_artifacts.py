"""Persist evidence-backed research artifacts with task provenance."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260812_04"
down_revision = "20260812_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create artifact storage without rewriting prior task results."""
    bind = op.get_bind()
    if "research_artifacts" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "research_artifacts",
        sa.Column("artifact_uid", sa.String(), primary_key=True),
        sa.Column("project_uid", sa.String(), nullable=False),
        sa.Column("session_uid", sa.String(), nullable=False),
        sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("task_uid", sa.String(), sa.ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index(
        "idx_research_artifacts_project",
        "research_artifacts",
        ["project_uid", "session_uid", "created_at"],
    )


def downgrade() -> None:
    """Drop only the additive artifact table introduced by this revision."""
    op.drop_index("idx_research_artifacts_project", table_name="research_artifacts")
    op.drop_table("research_artifacts")
