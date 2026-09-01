"""Create research feedback-loop tables: signal events, analysis queue, clicks."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260901_11"
down_revision = "20260815_10"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _existing_tables()
    if "feedback_analysis_tasks" not in tables:
        op.create_table(
            "feedback_analysis_tasks",
            sa.Column("task_uid", sa.String(), primary_key=True),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("user_uuid", sa.String(), nullable=False),
            sa.Column("project_uid", sa.String(), nullable=False),
            sa.Column("session_uid", sa.String(), nullable=False),
            sa.Column("citation_audit", sa.String(), nullable=False, server_default=""),
            sa.Column("retrieved_evidence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_doc_uids_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )
        op.create_index("idx_feedback_analysis_status", "feedback_analysis_tasks", ["status", "updated_at"])
    if "feedback_events" not in tables:
        op.create_table(
            "feedback_events",
            sa.Column("event_uid", sa.String(), primary_key=True),
            sa.Column("user_uuid", sa.String(), nullable=False),
            sa.Column("project_uid", sa.String(), nullable=False),
            sa.Column("session_uid", sa.String(), nullable=False),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("signal_type", sa.String(), nullable=False),
            sa.Column("prompt_digest", sa.String(), nullable=False),
            sa.Column("doc_uid", sa.String(), nullable=False, server_default=""),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(), nullable=False),
        )
        op.create_index(
            "idx_feedback_events_bucket",
            "feedback_events",
            ["project_uid", "signal_type", "doc_uid", "created_at"],
        )
        op.create_index("idx_feedback_events_run", "feedback_events", ["run_uid"])
    if "agent_evidence_clicks" not in tables:
        op.create_table(
            "agent_evidence_clicks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("user_uuid", sa.String(), nullable=False),
            sa.Column("project_uid", sa.String(), nullable=False),
            sa.Column("evidence_ref", sa.String(), nullable=False),
            sa.Column("item_uid", sa.String(), nullable=False, server_default=""),
            sa.Column("created_at", sa.String(), nullable=False),
        )
        op.create_index("idx_agent_evidence_clicks_run", "agent_evidence_clicks", ["run_uid", "created_at"])


def downgrade() -> None:
    tables = _existing_tables()
    if "agent_evidence_clicks" in tables:
        op.drop_index("idx_agent_evidence_clicks_run", table_name="agent_evidence_clicks")
        op.drop_table("agent_evidence_clicks")
    if "feedback_events" in tables:
        op.drop_index("idx_feedback_events_run", table_name="feedback_events")
        op.drop_index("idx_feedback_events_bucket", table_name="feedback_events")
        op.drop_table("feedback_events")
    if "feedback_analysis_tasks" in tables:
        op.drop_index("idx_feedback_analysis_status", table_name="feedback_analysis_tasks")
        op.drop_table("feedback_analysis_tasks")
