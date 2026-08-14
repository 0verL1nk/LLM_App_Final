"""Create durable runtime tables for fresh databases under Alembic ownership."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260812_03"
down_revision = "20260809_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Run/Task runtime schema when upgrading an empty database."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_runs" not in tables:
        op.create_table(
            "agent_runs",
            sa.Column("run_uid", sa.String(), primary_key=True),
            sa.Column("project_uid", sa.String(), nullable=False),
            sa.Column("session_uid", sa.String(), nullable=False),
            sa.Column("uuid", sa.String(), nullable=False),
            sa.Column("client_request_id", sa.String(), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
            sa.UniqueConstraint("uuid", "client_request_id", name="uq_agent_runs_request"),
        )
        op.create_index("idx_agent_runs_session", "agent_runs", ["uuid", "project_uid", "session_uid", "created_at"])
    tables.add("agent_runs")
    if "agent_run_events" not in tables:
        op.create_table(
            "agent_run_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("event_uid", sa.String(), nullable=False, unique=True),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("timestamp", sa.String(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("item_uid", sa.String()),
            sa.Column("task_uid", sa.String()),
            sa.UniqueConstraint("run_uid", "sequence", name="uq_agent_run_events_sequence"),
        )
        op.create_index("idx_agent_run_events_sequence", "agent_run_events", ["run_uid", "sequence"])
    if "agent_run_items" not in tables:
        op.create_table(
            "agent_run_items",
            sa.Column("item_uid", sa.String(), primary_key=True),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("task_uid", sa.String()),
            sa.Column("item_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )
        op.create_index("idx_agent_run_items_run", "agent_run_items", ["run_uid", "created_at"])
    if "agent_tasks" not in tables:
        op.create_table(
            "agent_tasks",
            sa.Column("task_uid", sa.String(), primary_key=True),
            sa.Column("run_uid", sa.String(), sa.ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_task_uid", sa.String(), sa.ForeignKey("agent_tasks.task_uid", ondelete="CASCADE")),
            sa.Column("parent_task_key", sa.String(), nullable=False, server_default=""),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("agent_role", sa.String(), nullable=False, server_default=""),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("idempotency_key", sa.String(), nullable=False),
            sa.Column("continuation_epoch", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("input_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_attempt_uid", sa.String()),
            sa.Column("cancel_requested_at", sa.String()),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("started_at", sa.String()),
            sa.Column("finished_at", sa.String()),
            sa.Column("updated_at", sa.String(), nullable=False),
            sa.UniqueConstraint("run_uid", "parent_task_key", "idempotency_key", name="uq_agent_tasks_idempotency"),
        )
        op.create_index("idx_agent_tasks_runnable", "agent_tasks", ["status", "created_at"])
        op.create_index("idx_agent_tasks_parent", "agent_tasks", ["parent_task_uid", "created_at"])
    if "agent_task_attempts" not in tables:
        op.create_table(
            "agent_task_attempts",
            sa.Column("attempt_uid", sa.String(), primary_key=True),
            sa.Column("task_uid", sa.String(), sa.ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("worker_id", sa.String(), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("lease_expires_at", sa.String(), nullable=False),
            sa.Column("heartbeat_at", sa.String(), nullable=False),
            sa.Column("started_at", sa.String()),
            sa.Column("finished_at", sa.String()),
            sa.Column("error_category", sa.String(), nullable=False, server_default=""),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
            sa.UniqueConstraint("task_uid", "attempt_number", name="uq_agent_task_attempts_number"),
        )
        op.create_index("idx_agent_task_attempts_lease", "agent_task_attempts", ["status", "lease_expires_at"])
    if "agent_task_outbox" not in tables:
        op.create_table(
            "agent_task_outbox",
            sa.Column("outbox_uid", sa.String(), primary_key=True),
            sa.Column("task_uid", sa.String(), sa.ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("available_at", sa.String(), nullable=False),
            sa.Column("lease_expires_at", sa.String()),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("published_at", sa.String()),
        )
        op.create_index("idx_agent_task_outbox_pending", "agent_task_outbox", ["status", "available_at"])


def downgrade() -> None:
    """Runtime tables are additive; production downgrade must use a backup restore."""
    raise RuntimeError("Runtime table downgrade is not supported; restore a database backup instead")
