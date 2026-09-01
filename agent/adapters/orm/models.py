"""SQLAlchemy Core table contracts for incrementally migrated runtime state."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

agent_runs = Table(
    "agent_runs",
    metadata,
    Column("run_uid", String, primary_key=True),
    Column("project_uid", String, nullable=False),
    Column("session_uid", String, nullable=False),
    Column("uuid", String, nullable=False),
    Column("client_request_id", String, nullable=False),
    Column("prompt", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("error_message", Text, nullable=False, server_default=""),
    Column("requested_mode", String, nullable=False, server_default="auto"),
    Column("resolved_mode", String, nullable=False, server_default="react"),
    Column("route_reason", String, nullable=False, server_default="legacy_default"),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("uuid", "client_request_id", name="uq_agent_runs_request"),
)
Index("idx_agent_runs_session", agent_runs.c.uuid, agent_runs.c.project_uid, agent_runs.c.session_uid, agent_runs.c.created_at)

agent_run_events = Table(
    "agent_run_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_uid", String, nullable=False, unique=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event_type", String, nullable=False),
    Column("timestamp", String, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("schema_version", Integer, nullable=False, server_default="1"),
    Column("item_uid", String),
    Column("task_uid", String),
    UniqueConstraint("run_uid", "sequence", name="uq_agent_run_events_sequence"),
)
Index("idx_agent_run_events_sequence", agent_run_events.c.run_uid, agent_run_events.c.sequence)

agent_run_items = Table(
    "agent_run_items",
    metadata,
    Column("item_uid", String, primary_key=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("task_uid", String),
    Column("item_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("idx_agent_run_items_run", agent_run_items.c.run_uid, agent_run_items.c.created_at)

agent_tasks = Table(
    "agent_tasks",
    metadata,
    Column("task_uid", String, primary_key=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("parent_task_uid", String, ForeignKey("agent_tasks.task_uid", ondelete="CASCADE")),
    Column("parent_task_key", String, nullable=False, server_default=""),
    Column("kind", String, nullable=False),
    Column("agent_role", String, nullable=False, server_default=""),
    Column("status", String, nullable=False),
    Column("idempotency_key", String, nullable=False),
    Column("continuation_epoch", Integer, nullable=False, server_default="0"),
    Column("input_json", Text, nullable=False, server_default="{}"),
    Column("result_json", Text, nullable=False, server_default="{}"),
    Column("error_message", Text, nullable=False, server_default=""),
    Column("current_attempt_uid", String),
    Column("cancel_requested_at", String),
    Column("created_at", String, nullable=False),
    Column("started_at", String),
    Column("finished_at", String),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("run_uid", "parent_task_key", "idempotency_key", name="uq_agent_tasks_idempotency"),
)
Index("idx_agent_tasks_runnable", agent_tasks.c.status, agent_tasks.c.created_at)
Index("idx_agent_tasks_parent", agent_tasks.c.parent_task_uid, agent_tasks.c.created_at)

research_artifacts = Table(
    "research_artifacts",
    metadata,
    Column("artifact_uid", String, primary_key=True),
    Column("project_uid", String, nullable=False),
    Column("session_uid", String, nullable=False),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("task_uid", String, ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False, unique=True),
    Column("artifact_type", String, nullable=False),
    Column("content_json", Text, nullable=False),
    Column("evidence_refs_json", Text, nullable=False, server_default="[]"),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("idx_research_artifacts_project", research_artifacts.c.project_uid, research_artifacts.c.session_uid, research_artifacts.c.created_at)

research_plans = Table(
    "research_plans",
    metadata,
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("goal", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

research_plan_steps = Table(
    "research_plan_steps",
    metadata,
    Column("run_uid", String, ForeignKey("research_plans.run_uid", ondelete="CASCADE"), primary_key=True),
    Column("step_id", String, primary_key=True),
    Column("title", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("depends_on_json", Text, nullable=False, server_default="[]"),
    Column("lane", String, nullable=False),
    Column("task_uid", String, ForeignKey("agent_tasks.task_uid", ondelete="SET NULL")),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("idx_research_plan_steps_task", research_plan_steps.c.task_uid)

agent_task_attempts = Table(
    "agent_task_attempts",
    metadata,
    Column("attempt_uid", String, primary_key=True),
    Column("task_uid", String, ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False),
    Column("worker_id", String, nullable=False),
    Column("attempt_number", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("lease_expires_at", String, nullable=False),
    Column("heartbeat_at", String, nullable=False),
    Column("started_at", String),
    Column("finished_at", String),
    Column("error_category", String, nullable=False, server_default=""),
    Column("error_message", Text, nullable=False, server_default=""),
    Column("result_json", Text, nullable=False, server_default="{}"),
    UniqueConstraint("task_uid", "attempt_number", name="uq_agent_task_attempts_number"),
)
Index("idx_agent_task_attempts_lease", agent_task_attempts.c.status, agent_task_attempts.c.lease_expires_at)

agent_task_outbox = Table(
    "agent_task_outbox",
    metadata,
    Column("outbox_uid", String, primary_key=True),
    Column("task_uid", String, ForeignKey("agent_tasks.task_uid", ondelete="CASCADE"), nullable=False),
    Column("event_type", String, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("available_at", String, nullable=False),
    Column("lease_expires_at", String),
    Column("created_at", String, nullable=False),
    Column("published_at", String),
)
Index("idx_agent_task_outbox_pending", agent_task_outbox.c.status, agent_task_outbox.c.available_at)

steering_inputs = Table(
    "agent_steering_inputs",
    metadata,
    Column("input_uid", String, primary_key=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("project_uid", String, nullable=False),
    Column("session_uid", String, nullable=False),
    Column("uuid", String, nullable=False),
    Column("client_request_id", String, nullable=False),
    Column("text", String, nullable=False),
    Column("status", String, nullable=False),
    Column("injected_at", String),
    Column("confirmed_at", String),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("uq_agent_steering_inputs_request", steering_inputs.c.uuid, steering_inputs.c.client_request_id, unique=True)
Index("idx_agent_steering_inputs_run", steering_inputs.c.run_uid, steering_inputs.c.status, steering_inputs.c.created_at)

context_memory_items = Table(
    "context_memory_items", metadata,
    Column("memory_uid", String, primary_key=True),
    Column("uuid", String, nullable=False),
    Column("project_uid", String, nullable=False, server_default=""),
    Column("session_uid", String, nullable=False, server_default=""),
    Column("memory_level", String, nullable=False),
    Column("memory_type", String, nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    Column("content", Text, nullable=False),
    Column("source_run_uid", String, nullable=False, server_default=""),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("expires_at", String, nullable=False, server_default=""),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("idx_context_memory_scope", context_memory_items.c.uuid, context_memory_items.c.project_uid, context_memory_items.c.memory_level, context_memory_items.c.updated_at)

session_context_summaries = Table(
    "session_context_summaries", metadata,
    Column("session_uid", String, primary_key=True),
    Column("project_uid", String, nullable=False),
    Column("uuid", String, nullable=False),
    Column("summary", Text, nullable=False),
    Column("source_run_uid", String, nullable=False, server_default=""),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("updated_at", String, nullable=False),
)
Index("idx_context_summary_scope", session_context_summaries.c.uuid, session_context_summaries.c.project_uid)

feedback_analysis_tasks = Table(
    "feedback_analysis_tasks",
    metadata,
    Column("task_uid", String, primary_key=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False, unique=True),
    Column("user_uuid", String, nullable=False),
    Column("project_uid", String, nullable=False),
    Column("session_uid", String, nullable=False),
    Column("citation_audit", String, nullable=False, server_default=""),
    Column("retrieved_evidence_count", Integer, nullable=False, server_default="0"),
    Column("evidence_doc_uids_json", Text, nullable=False, server_default="[]"),
    Column("status", String, nullable=False, server_default="pending"),
    Column("error_message", Text, nullable=False, server_default=""),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("idx_feedback_analysis_status", feedback_analysis_tasks.c.status, feedback_analysis_tasks.c.updated_at)

feedback_events = Table(
    "feedback_events",
    metadata,
    Column("event_uid", String, primary_key=True),
    Column("user_uuid", String, nullable=False),
    Column("project_uid", String, nullable=False),
    Column("session_uid", String, nullable=False),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("signal_type", String, nullable=False),
    Column("prompt_digest", String, nullable=False),
    Column("doc_uid", String, nullable=False, server_default=""),
    Column("payload_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
)
Index("idx_feedback_events_bucket", feedback_events.c.project_uid, feedback_events.c.signal_type, feedback_events.c.doc_uid, feedback_events.c.created_at)
Index("idx_feedback_events_run", feedback_events.c.run_uid)

evidence_clicks = Table(
    "agent_evidence_clicks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_uid", String, ForeignKey("agent_runs.run_uid", ondelete="CASCADE"), nullable=False),
    Column("user_uuid", String, nullable=False),
    Column("project_uid", String, nullable=False),
    Column("evidence_ref", String, nullable=False),
    Column("item_uid", String, nullable=False, server_default=""),
    Column("created_at", String, nullable=False),
)
Index("idx_agent_evidence_clicks_run", evidence_clicks.c.run_uid, evidence_clicks.c.created_at)


__all__ = [
    "agent_run_events",
    "agent_run_items",
    "agent_runs",
    "research_artifacts",
    "research_plans",
    "research_plan_steps",
    "agent_task_attempts",
    "agent_task_outbox",
    "agent_tasks",
    "evidence_clicks",
    "feedback_analysis_tasks",
    "feedback_events",
    "metadata",
    "steering_inputs",
    "context_memory_items",
    "session_context_summaries",
]
