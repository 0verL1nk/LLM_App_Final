"""Create governed L2-L4 memory storage and import legacy project memories."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_07"
down_revision = "20260814_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_memory_items",
        sa.Column("memory_uid", sa.String(), primary_key=True),
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("project_uid", sa.String(), nullable=False, server_default=""),
        sa.Column("session_uid", sa.String(), nullable=False, server_default=""),
        sa.Column("memory_level", sa.String(), nullable=False),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_run_uid", sa.String(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_context_memory_scope", "context_memory_items", ["uuid", "project_uid", "memory_level", "updated_at"])
    op.create_table(
        "session_context_summaries",
        sa.Column("session_uid", sa.String(), primary_key=True),
        sa.Column("project_uid", sa.String(), nullable=False),
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_run_uid", sa.String(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_context_summary_scope", "session_context_summaries", ["uuid", "project_uid"])
    names = set(sa.inspect(op.get_bind()).get_table_names())
    if "memory_items" in names:
        op.execute(
            "INSERT INTO context_memory_items "
            "(memory_uid, uuid, project_uid, session_uid, memory_level, memory_type, title, content, source_run_uid, version, expires_at, created_at, updated_at) "
            "SELECT memory_uid, uuid, project_uid, COALESCE(session_uid, ''), 'L3', memory_type, COALESCE(title, ''), content, '', 1, COALESCE(expires_at, ''), created_at, updated_at FROM memory_items "
            "WHERE NOT EXISTS (SELECT 1 FROM context_memory_items WHERE context_memory_items.memory_uid = memory_items.memory_uid)"
        )


def downgrade() -> None:
    op.drop_index("idx_context_summary_scope", table_name="session_context_summaries")
    op.drop_table("session_context_summaries")
    op.drop_index("idx_context_memory_scope", table_name="context_memory_items")
    op.drop_table("context_memory_items")
