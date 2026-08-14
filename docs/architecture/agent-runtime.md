# Agent Runtime Architecture

## Canonical path

```text
web (TanStack Query)
  -> api (FastAPI transport)
  -> agent.application.agent_center
  -> agent.session_factory.create_agent_session
  -> agent.runtime_agent.create_runtime_agent
  -> LangChain create_agent
```

`ResearchWorkspaceService` is the canonical Web turn entry and
`create_agent_session` remains the only Agent construction entry. The service
resolves project scope, model configuration, memory context, persistence, and
runtime caching. `AgentSession` owns the checkpointer connection and is closed on
API shutdown.

## Production dispatch target

For multi-instance deployment, a Run is represented by a top-level `LEADER` task
and dispatched through `agent_task_outbox`. `Run` remains the ordered interaction
and event owner; a worker database lease is the only execution authority. Do not add a
second Run-specific outbox or treat a web/API process's in-memory queue as reliable
state. The submission transaction now creates the Run, its `LEADER` task, and the
outbox record together; local direct background invocation is still only a
development transport. A supervised worker/outbox publisher is required before a
multi-instance deployment claim.

The current supervised entry point is `python -m agent.application.task_worker_host`.
It derives claimable kinds from its injected `TaskExecutorRegistry`, reclaims expired
outbox and task leases, and executes the addressed task under the same task lease.
The default registry provides Leader, configured Subagent and continuation executors;
an extension registers a new kind without changing the durable schema or worker loop.

`PAPERSAGE_TASK_TRANSPORT=outbox` is required for a multi-instance deployment: API
processes then only persist the Run/task/outbox transaction. The default `local` mode
is retained for desktop and development and merely nudges the same addressed task;
it never becomes the execution authority.

## Delegation model

Subagent definitions live in `agent/subagent/*/agent.md` and are validated fail-fast at startup. The Leader exposes `delegate_task`: it persists an `AgentTask` with a stable `task_uid`, an outbox record, and a V2 `agent_task` item. The worker dynamically resolves its executor from an open persisted task kind; subagent tasks alone are then resolved by persisted role through an injected registry, rather than a role/description correlation or a process-global task registry. Invalid definitions prevent runtime construction instead of silently dropping a role.

| Role | Purpose | Capabilities |
|---|---|---|
| researcher | Gather and reconcile evidence | project documents, web/paper search, skills |
| reviewer | Independently challenge claims | project documents, skills |
| writer | Produce constrained prose | skills |

Subagents do not receive delegation middleware, so delegation cannot recurse. The Leader may call the same role multiple times; identity is always `task_uid`.

## Observability and evaluation

Task state and V2 items are the UI and replay source of truth; roles and descriptions are never used to correlate child lifecycle.

Researcher outputs must preserve document `<evidence>...</evidence>` locators or external URLs. These references are attached to each observed delegated task, displayed in the UI, and remain available to evals.

When joined child tasks finish, the continuation input includes a conservative
`evidence_merge`: it deduplicates exact evidence IDs but retains each sourced claim.
Only explicit-negation claim pairs are flagged automatically; all other possible
disagreements remain separate for Leader review. The merge is persisted as an
`evidence_merge` research artifact and the inspector renders its claims, open
questions, and unresolved conflicts from that API fact.

## Runtime state ownership

- `update_plan` owns the only optional execution-plan snapshot: revision, goal and typed
  steps (dependency, lane, task link and status). There is no Todo sidecar state or
  compatibility tool. Durable Runs also persist that snapshot in `research_plans` and
  `research_plan_steps`; a linked task can only claim after its dependencies complete,
  and its claimed/terminal transition updates the step in the same database transaction.
- LangChain `SummarizationMiddleware` exclusively owns active graph message compaction. Project long-term memory remains a separate retrieval layer injected per turn.
- A completed turn creates a durable `memory_events` record and enqueues `process_memory_event`. A structured-output consolidation model decides create/update/delete operations; deterministic code only validates schema and project/user scope. Retrieval uses semantic embeddings rather than keyword overlap.
- `ask_human` is a Leader-only capability. A submitted UI response becomes an explicit confirmation message in the same checkpoint thread.

## RAG ingestion and dynamic loading

File upload persists metadata and immediately enqueues `process_document_ingestion`.
The durable `rag_ingestions` record exposes `queued`, `extracting`, `ocr`,
`loading_model`, `chunking`, `embedding`, `publishing`, `ready`, and `failed` state.
Image-only PDFs use local RapidOCR ONNX small models and report completed/total pages.
Embedding progress
uses completed/total chunk counts; stages without measurable work never invent a
percentage.

Each document is chunked and embedded in full, then its versioned rows are published
to embedded LanceDB. Only after publication succeeds does SQLite mark the ingestion
record `ready`; retrieval filters by the exact ready `(doc_uid, index_version)`
manifest, so partial or stale versions cannot leak into results. The canonical
LanceDB query retrieves dense-vector and FTS/BM25 candidates separately, fuses them
by chunk ID with reciprocal-rank fusion, then applies FlashRank. If reranking cannot
run, the trace records `rerank_skipped` and returns the RRF order without inventing a
rerank score.
`DynamicProjectEvidenceService` reloads the ready manifest on every tool call, so
Agent sessions and checkpoint threads remain independent of extraction and index
updates. A legacy ready row without LanceDB data is automatically requeued.

## Provider message invariant

Every model request has at most one provider-facing `SystemMessage`, stored in
`ModelRequest.system_message`. Middleware must merge dynamic instructions into that
message with `request.override(system_message=...)`; it must never insert system
messages into conversation history. `TurnContextMiddleware` stages per-turn context
in typed graph state, and the innermost LLM logger records the final payload.

## Async boundary

Subagent calls are request-scoped. Memory consolidation is detached from response latency: RQ is used when workers are available, otherwise a local thread executor is used, and this path never falls back to synchronous model execution. `memory_events.status/error_message` provides durable completion and retry state. General pause/resume workflows still require a durable workflow deployment.
## Steering input queue

An active Run may accept durable user follow-ups through
`POST /projects/{project_uid}/sessions/{session_uid}/steering-inputs`. The input is
not a parallel Run: it is a user-owned SQLite record and a V2 `human_request` item.
The runtime drains a batch only after a tool result and immediately before the next
model call. It confirms the batch only after that model call succeeds; unconfirmed
delivery is replayable after interruption. The browser's Queue component reads those
V2 items and never invents queue progress.

If an Agent produces its final response without a subsequent tool boundary, unconfirmed
input is atomically moved to an idempotent successor Run. That Run is dispatched through
the same durable task/outbox path and confirms the input on its first successful model
call; no browser-side retry or in-memory handoff is authoritative.

## Execution modes and context memory

Every Run persists both its requested mode (`auto`, `react`, `plan_execute`, or
`agent_teams`) and resolved mode plus route reason. The worker reconstructs the
corresponding capability profile; continuations reuse the persisted resolved mode.

Long-lived context now has SQLAlchemy/Alembic storage: L2 session summaries, L3
project-scoped memories, and L4 user preferences. L4 rows use an empty project scope
and cannot be read through another user's scope. Legacy project memories are imported
by the migration; new retrieval reads the governed L3/L4 tables.
