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

## Delegation model

The paper leader registers Deep Agents `SubAgentMiddleware`, which exposes the official `task` tool. Subagent definitions live in `agent/subagent/*/agent.md` and are validated fail-fast at startup. Invalid definitions prevent runtime construction instead of silently dropping a role.

| Role | Purpose | Capabilities |
|---|---|---|
| researcher | Gather and reconcile evidence | project documents, web/paper search, skills |
| reviewer | Independently challenge claims | project documents, skills |
| writer | Produce constrained prose | skills |

Subagents do not receive `task`, Todo, or Plan middleware, so delegation cannot recurse. The Leader may call the same subagent type multiple times. Independent `task` calls emitted in one model response are eligible for concurrent execution, but the Leader waits for their ToolMessages before synthesis; these are request-scoped concurrent calls, not detached jobs.

## Observability and evaluation

`SubagentLifecycleMiddleware` emits start/completion timestamps and completion notifications. `build_delegation_execution` combines those observations with actual `task` calls and matching ToolMessages. `parallel` is true only when measured execution intervals overlap; `parallel_requested` records multiple calls emitted together. The same structure feeds trace events, UI status, metrics, and eval contracts. No keyword router or static role list may claim that delegation occurred.

Researcher outputs must preserve document `<evidence>...</evidence>` locators or external URLs. These references are attached to each observed delegated task, displayed in the UI, and remain available to evals.

## Runtime state ownership

- `write_todos` state is the only Todo source. The UI persists and renders graph state; no sidecar Todo JSON file is used.
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
manifest, so partial or stale versions cannot leak into results. LanceDB performs
native dense-vector plus full-text hybrid search with reciprocal-rank fusion.
`DynamicProjectEvidenceService` reloads the ready manifest on every tool call, so
Agent sessions and checkpoint threads remain independent of extraction and index
updates. A legacy ready row without LanceDB data is automatically requeued.

## Provider message invariant

Every model request has at most one provider-facing `SystemMessage`, stored in
`ModelRequest.system_message`. Middleware must merge dynamic instructions into that
message with `request.override(system_message=...)`; it must never insert system
messages into conversation history. `TurnContextMiddleware` stages per-turn context
in typed graph state, Todo adds its planning contract at request time, and the
innermost LLM logger records the final payload after those merges.

## Async boundary

Subagent calls are request-scoped. Memory consolidation is detached from response latency: RQ is used when workers are available, otherwise a local thread executor is used, and this path never falls back to synchronous model execution. `memory_events.status/error_message` provides durable completion and retry state. General pause/resume workflows still require a durable workflow deployment.
