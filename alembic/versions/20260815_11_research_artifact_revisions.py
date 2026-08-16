"""Revisioned research artifacts with source provenance for writing and memory."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260815_11"
down_revision = "20260815_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Widen artifact ownership and add the append-only revision table."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    columns = {column["name"] for column in sa.inspect(bind).get_columns("research_artifacts")}
    with op.batch_alter_table("research_artifacts") as batch:
        if "uuid" not in columns:
            batch.add_column(sa.Column("uuid", sa.String(), nullable=False, server_default=""))
        if "validity_scope" not in columns:
            batch.add_column(sa.Column("validity_scope", sa.Text(), nullable=False, server_default=""))
        if "update_policy" not in columns:
            batch.add_column(sa.Column("update_policy", sa.Text(), nullable=False, server_default=""))
        batch.alter_column("run_uid", existing_type=sa.String(), nullable=True)
        batch.alter_column("task_uid", existing_type=sa.String(), nullable=True)
    # Existing task-derived artifacts inherit their owner from the owning Run.
    op.execute(
        """
        UPDATE research_artifacts
        SET uuid = (SELECT agent_runs.uuid FROM agent_runs WHERE agent_runs.run_uid = research_artifacts.run_uid)
        WHERE uuid = '' AND run_uid IS NOT NULL
        """
    )
    if "research_artifact_revisions" not in tables:
        op.create_table(
            "research_artifact_revisions",
            sa.Column("revision_uid", sa.String(), primary_key=True),
            sa.Column(
                "artifact_uid",
                sa.String(),
                sa.ForeignKey("research_artifacts.artifact_uid", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
            sa.Column("content_json", sa.Text(), nullable=False),
            sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("source_run_uid", sa.String(), nullable=False, server_default=""),
            sa.Column("source_task_uid", sa.String(), nullable=False, server_default=""),
            sa.Column("based_on_revision_uid", sa.String(), nullable=False, server_default=""),
            sa.Column("decision_note", sa.Text(), nullable=False, server_default=""),
            sa.Column("decided_at", sa.String(), nullable=False, server_default=""),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.UniqueConstraint("artifact_uid", "revision", name="uq_research_artifact_revisions_number"),
        )
        op.create_index(
            "idx_research_artifact_revisions_artifact",
            "research_artifact_revisions",
            ["artifact_uid", "revision"],
        )


def downgrade() -> None:
    op.drop_index(
        "idx_research_artifact_revisions_artifact",
        table_name="research_artifact_revisions",
    )
    op.drop_table("research_artifact_revisions")
    with op.batch_alter_table("research_artifacts") as batch:
        batch.alter_column("run_uid", existing_type=sa.String(), nullable=False)
        batch.alter_column("task_uid", existing_type=sa.String(), nullable=False)
        batch.drop_column("update_policy")
        batch.drop_column("validity_scope")
        batch.drop_column("uuid")
