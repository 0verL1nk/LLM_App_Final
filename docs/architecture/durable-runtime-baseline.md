# Durable Runtime Baseline (Guardrails)

This document records the pre-migration baseline for the
`durable-research-agent-runtime` change (task section 0). It captures the
confirmed active Run path, the recorded fixture metrics, the
freeze that guards the canonical path.

## Confirmed Run path, worker, queue and middleware

`tests/integration/test_run_path_baseline.py` asserts the following through the
real middleware stack (a binding fake chat model against a disposable SQLite
database); a failure there means a baseline behavior changed:

1. **Web Run path.** The web client creates Runs through
   `POST /api/v1/projects/{project_uid}/sessions/{session_uid}/runs` (202) and
   consumes `GET /runs/{run_uid}/events` / `GET /runs/{run_uid}/items`. The
   legacy `POST .../turns` endpoint still executes in the API process and is
   not the web path.
2. **Dispatch topology.** `prepare_turn_run` atomically persists the user
   message, the Run, one top-level `AgentTask(kind=leader)` and its outbox row
   (`create_leader_run`). The API process never owns execution.
3. **Worker implementation.** `agent.application.task_worker_host.TaskOutboxWorker`
   is the supervised entry: reclaim expired outbox claims and attempts,
   reconcile waiting-child joins / completed continuations / evidence
   artifacts, then lease one outbox record and execute it through
   `LeaseTaskWorker` + `TaskExecutorRegistry`. A second `run_once()` is idle
   after a completed leader run. `python -m agent.application.task_worker_host`
   polls forever (`PAPERSAGE_WORKER_ID`, `PAPERSAGE_TASK_POLL_SECONDS`,
   `PAPERSAGE_DATABASE`).
4. **Queue configuration.** `PAPERSAGE_TASK_TRANSPORT` defaults to `local`
   (API nudges `utils.task_queue.enqueue_background_task`, dev-only; the local
   pool default is `LOCAL_TASK_MAX_WORKERS=2` and is shared with ingestion /
   title / memory work). `outbox` is the production setting: `dispatch_task`
   is a no-op and only the worker polls. Any other value fails hard.
5. **Leader profile middleware.** `agent_teams` mode resolves to
   `paper_leader_profile` with `middleware_ids = ("trace", "llm_logger",
   "subagent", "plan")`; `build_middleware_list` yields `TraceMiddleware`,
   `DurableDelegationMiddleware` (flag-gated, see below),
   `plan_middleware` and `llm_logger_middleware` innermost.
6. **Reconnect replay.** `GET /runs/{run_uid}/events?afterSeq=N` replays only
   later events in strict sequence order and terminates once a terminal run
   has no new events.

## Recorded baseline metrics

Harness: `agent/adapters/orm/baseline_metrics_repository.get_baseline_metrics`
(reads `agent_runs`, `agent_tasks`, `agent_task_attempts`, `agent_run_events`).

```bash
uv run python -m scripts.durable_runtime_baseline --database ./database.sqlite
uv run python -m scripts.durable_runtime_baseline --database ./db.sqlite --format json
```

Metric definitions:

| Metric | Definition |
| --- | --- |
| run success/failure | `runs.status_counts` plus `success_rate = completed / terminal` |
| stalled runs | runs still `queued/running/waiting_children` with `updated_at` older than `stalled_after_seconds` (default 300) |
| delegation count | tasks with `kind = 'subagent'` |
| duplicate events | `(run_uid, event_type)` groups of duplicated terminal `run.*` events and `(run_uid, item_uid)` groups of duplicated terminal `item.*` events |
| reconnect recovery | runs with a `run.resumed` event, split into completed vs still unfinished |
| median task latency | median / p95 of `finished_at - started_at` over finished attempts |

Fixture record (deterministic fixture asserted by
`tests/unit/test_durable_runtime_baseline.py`; five runs, seven tasks):

```text
# Durable runtime baseline - tmp/baseline-fixture.sqlite

- generated_at: 2026-08-15T05:32:30Z (fixture regeneration timestamp)
- stalled_after_seconds: 300.0
- runs: total=5 status={'completed': 2, 'failed': 1, 'queued': 2}
- run_success_rate: 0.6667
- stalled_runs: 1
- tasks: total=7 status={'queued': 7}
- delegation_count: 2
- events_total: 14
- duplicate_lifecycle_events: [{'run_uid': 'run_...', 'event_type': 'run.failed', 'occurrences': 2}]
- duplicate_item_terminal_events: [{'run_uid': 'run_...', 'item_uid': 'item_agent_task_task_...', 'occurrences': 2}]
- reconnect_recovery: {'resumed_runs': 2, 'resumed_completed': 1, 'resumed_unfinished': 1}
- task_latency_ms: {'samples': 3, 'median': 200.0, 'p95': 300.0}
```


Default: **off**. The flag gates *new delegation capability*: while disabled,
`build_middleware_list` does not register `DurableDelegationMiddleware`, so the
Leader has no `delegate_task` tool and creates no child tasks or continuations.
Direct answers, plan steps, tools and the durable leader dispatch (`POST /runs`
creating the LEADER task and outbox row) keep working.

Resolution order (`agent/application/feature_flags.durable_agent_tasks_enabled`):

   scope; `false|0|no|off` — disabled for every scope (kill switch that
   overrides stored overrides).
2. Otherwise stored overrides in the `agent_feature_flags` table
   (`agent/adapters/orm/feature_flag_repository.py`):
   project scope wins over user scope; either may enable. Managed with:

   ```python
   from agent.adapters.orm.feature_flag_repository import set_feature_flag
                    scope_type="project", scope_id="<project_uid>", enabled=True)
   ```

3. Otherwise off.

Each created Run records the resolved value in its leader task input payload
(`durable_agent_tasks`), so run facts always show which capability set a Run
started with.

### Disabling without a deployment rollback

  setting) in the process environment and restart API/worker processes. This
  overrides any stored override.
- **Cohort:** `set_feature_flag(..., enabled=False)` (or `clear_feature_flag`)
   for the user/project scope. Takes effect for newly built agent sessions;
   call the existing settings update path (which invalidates cached sessions)
   or restart processes to force it.

Rollback semantics (by design): disabling affects only new Runs/sessions.
Already persisted tasks, continuations and their workers always finish or
cancel from the durable tables; existing Run history stays readable.

## Architecture freeze

`tests/unit/test_architecture_boundaries.py` fails the build when:

- any `agent/**` module imports legacy `team` / `a2a` machinery or the symbols
  `TeamRuntime`, `build_delegation_execution`, `A2A` (the legacy
  `agent/team/` package is deleted and must not return);
- any `agent/**` module imports `concurrent.futures` or `multiprocessing`
  (no new thread/process pools in the canonical path);
- a new `agent/**` module imports `utils.task_queue` directly — only the three
  grandfathered consumers (`agent_center/memory.py`, `session_titles.py`,
  `task_delivery.py`) may; new code must go through
  `agent.application.task_delivery.dispatch_task`;
- the durable task-authority modules
  (`task_dispatcher`, `task_worker_host`, `task_delivery`, `delegation_service`,
  `leader_task_executor`, `subagent_task_executor`, `steering_inputs`,
  `research_workspace`, `feature_flags`) grow module-level mutable containers:
  task authority lives in the database, never in process globals.
