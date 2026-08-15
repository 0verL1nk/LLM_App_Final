# Implementation Tasks

## 0. Guardrails and baseline

- [x] Confirm the active web Run path, worker implementation, queue configuration and
  actual `paper_leader_profile` middleware through integration tests before edits.
- [x] Record baseline metrics: run success/failure, stalled runs, delegation count,
  duplicate events, reconnect recovery and median task latency.
- [x] Add a feature flag `DURABLE_AGENT_TASKS_ENABLED`, default off, scoped by user
  or project; document how to disable it without a deployment rollback.
- [x] Freeze new use of legacy A2A, TeamRuntime, process globals and thread pools;
  add an architecture test that rejects new imports in the canonical path.

## 1. Domain contracts and persistence

- [x] Define typed domain models for open-kind `AgentTask`, `AgentTaskAttempt`,
  `ResearchPlan`, `ResearchPlanStep`, `RunItem`, V2 event envelopes and terminal
  error categories. Keep UI schemas generated/validated from the same contract.
- [x] Add SQLite migrations for task, attempt, plan-step, item and outbox tables;
  add indexes for `(run_uid, sequence)`, runnable tasks, parent/child lookup and
  lease recovery.
- [x] Implement repositories with ownership-aware read methods and transactional
  state transitions. Require compare-and-set status/lease ownership for claims and
  completion.
- [x] Implement append-event plus projection updates in one transaction; make the
  event sequence allocation safe under concurrent child completion.
- [x] Add repository tests for idempotent submit, duplicate dispatch, late completion,
  invalid transitions, cancellation races and projection rebuild.

## 2. Versioned event protocol

- [x] Define V2 item lifecycle and payload schemas for assistant text, reasoning
  summary, plan, tool call, agent task, human request, presentation and failure.
- [x] Implement a server projector from middleware/runtime facts to V2; reject unknown
  item type/status before persistence.
- [x] Build a temporary V2-to-V1 adapter for existing browser clients. Do not map
  lifecycle records into user-facing prose.
- [x] Add `GET /runs/{run_uid}/items` and V2 SSE negotiation/version handling while
  preserving ordered `afterSeq` replay.
- [x] Add contract tests for item started/delta/completed ordering, replay de-duplication,
  redaction and final Run terminal semantics.

## 3. Unified plan semantics

- [x] Create `update_plan` input schema with revision, explicit step IDs, dependency
  IDs, lane and optional task linkage; expose it only to the Leader.
- [x] Remove legacy `write_plan`/`write_todos` and the Todo graph; do not retain a
  forwarding compatibility path.
- [x] Update prompt instructions so the model plans only when useful and updates a
  declared step before/after substantive work; no keyword-based forced planning.
- [x] Bind task lifecycle transitions to plan-step transitions transactionally.
- [ ] Add tests for simple unplanned answers, sequential steps, explicit parallel
  lanes, blocked dependencies, replan after failure and old Todo snapshot reading.

## 4. Durable dispatcher and child Agent execution

- [x] Make `POST /runs` atomically create its `Run`, top-level `LEADER` Task and
  `task.dispatch_requested` outbox record. Remove direct API-process execution of a Run.
- [x] Add exact-task lease claiming for transport delivery; a queue payload identifies a
  task but worker correctness always comes from the database lease, not queue delivery.
- [x] Define `TaskDispatcher` and `TaskWorker` application ports; implement a local
  supervised worker using repository leases and an outbox/reconciler loop.
- [x] Add worker identity, heartbeat, bounded retry policy, exponential backoff and
  terminal error normalization. Do not retain task authority in memory.
- [x] Replace the canonical Leader `task` tool with `delegate_task` backed by task
  creation/outbox publishing. Keep role definitions and bounded capability manifests.
- [x] Execute child tasks with their own `task_uid`, configured role and child
  LangGraph thread/checkpoint. Prohibit recursive delegation in phase one.
- [x] Persist sanitized child result, evidence references and attempt metrics; use
  `task_uid` for every lifecycle correlation.
- [x] Add integration tests proving two identical-role, identical-description child
  tasks complete independently and notify the correct parent.

## 5. Parent continuation, cancellation and recovery

- [x] Persist parent checkpoint/continuation metadata at the `delegate_task` boundary.
- [x] Implement join-mode child completion fan-in, idempotent continuation task
  creation and ToolMessage injection into the original root thread.
- [x] Implement Run/Task cancel, retry, inspect and input API routes with ownership
  checks, safe worker cancellation and user-readable terminal events.
- [x] Implement startup reconciliation for queued work, expired leases, stuck
  `waiting_children` parents and orphaned continuation tasks.
- [x] Add crash/restart tests at each state boundary and a test that continuation runs
  once when concurrent child completion notifications race.

## 6. Web reducer and product UI

- [x] Add Zod schemas and a V2 reducer keyed by `(run_uid, sequence, item_uid)`;
  hydrate snapshot then subscribe from the latest sequence.
- [x] Replace legacy delegation reconstruction with V2 `agent_task` item rendering.
- [x] Feed AI Elements `Plan`, `Task`, `Tool`, `Reasoning` and `ChainOfThought` from
  the corresponding typed item only; keep detailed child attempts in the inspector.
- [x] Add cancel/retry controls only when server capabilities and task state allow
  them; show clear pending/cancelled/failed/retrying copy.
- [x] Add React tests for multiple same-role children, reconnect/replay, late event,
  cancelled task and V1 historical fallback.

## 7. Research artifacts, collaboration and writing

- [ ] Define Pydantic/Zod contracts for `EvidencePacket`, atomic claim, limitation,
  open question, `WritingBrief`, `DraftRevision` and claim-span provenance.
- [ ] Make evidence research, method review, cross-check and argument editing
  capability profiles emit validated packets; retain a concise narrative field but
  reject packet claims that cite outside the project/current web evidence scope.
- [ ] Implement Leader merge semantics: deduplicate evidence IDs, preserve conflicting
  claims, accumulate coverage gaps, and create follow-up tasks only by explicit
  Leader decision.
- [ ] Persist `ResearchArtifact` revisions with source run/task/evidence references;
  migrate the current memory consolidator incrementally rather than converting
  ungrounded chat summaries into facts.
- [ ] Add writing revision storage and APIs that preserve the original draft, attach
  claim spans to evidence, and support accept/reject/rewrite without destructive
  overwrite.
- [ ] Build research UI for packet evidence coverage, contradictions, open questions,
  draft citation gaps and source-coordinate preview. A2UI surfaces may visualize a
  validated ClaimGraph but cannot create facts.
- [ ] Add evals for paper explanation fidelity, cross-paper contradiction retention,
  evidence-backed drafting, unsupported-claim detection and memory provenance.

## 8. Cutover, cleanup and documentation

- [ ] Run dual-write shadow comparisons and publish a discrepancy report before
  enabling durable delegation for default users.
- [x] Remove `build_delegation_execution` role/description timing correlation,
  DeepAgents lifecycle-only UI source and obsolete V1-only tests after the migration
  window.
- [x] Archive/supersede inconsistent requirements in `refactor-multi-agent-system`;
  update canonical OpenSpec specs rather than leaving two active truths.
- [x] Update README, architecture diagrams, API documentation, operations runbook and
  `AGENTS.md`-referenced test commands.
- [ ] Run `bash scripts/quality_gate.sh core`, focused integration/eval suites,
  `pnpm --dir web test`, `pnpm --dir web typecheck`, lint, and an end-to-end browser
  reconnect scenario.

## Exit criteria

- [x] Multiple API/worker instances can receive duplicate leader-task delivery while
  exactly one attempt executes the Run; a terminated worker's lease is reclaimed.
  Shared-SQLite dual-worker coverage proves duplicate delivery ownership; process
  termination/restart coverage remains required.
- [x] A child task can be independently identified, retried, cancelled and recovered
  after process restart without duplicate parent continuation.
- [x] Multiple subagents of the same role can run concurrently without ambiguous UI,
  timing or result ownership.
- [x] Plan, tool, child task and message surfaces all derive from the same V2
  event/task contract.
- [x] A failed or cancelled task produces a durable, user-safe result and never leaves
  its parent Run indefinitely running.
- [x] Legacy session history remains readable and feature-flag rollback is verified.
- [ ] Every final paper fact and every draft factual claim can be traced to an evidence
  (superseded to research-scenario-pack per the section 7 note)
  packet and source location, or is visibly labelled as synthesis/uncertainty.
