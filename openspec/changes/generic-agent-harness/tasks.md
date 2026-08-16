# Implementation Tasks

## 0. Guardrails and baseline

- [ ] Capture the current delegation behavior in a regression test (free-text
  `[结论][证据][待验证点]` path through `submit_delegated_agent_task` and
  continuation) before any edit, so the pack migration is provably
  behavior-preserving where intended.
- [ ] Extend `tests/unit/test_architecture_boundaries.py`: runtime modules
  (`agent/application`, `agent/middlewares`, `agent/adapters`) must not import
  `agent.scenarios.*`; contracts resolve only through the registry; the
  `agent/subagent/` path must not return.
- [ ] Document in `docs/architecture/durable-runtime-baseline.md` that
  contracts/budget/routing ride the existing `DURABLE_AGENT_TASKS_ENABLED` flag
  and that no new flag is introduced.

## 1. Scenario pack framework

- [ ] Define `scenario.yaml` manifest schema (execution_mode, leader_profile,
  max_delegated_tasks_per_run, role_contracts) with fail-fast validation
  (unknown contract reference, duplicate role names, non-positive budget).
- [ ] Implement the pack loader: resolve execution mode → pack → roles, leader
  prompt, budget, contract table; migrate `agent/subagent/*/agent.md` and the
  leader prompt into `agent/scenarios/research/` in one atomic move.
- [ ] Add `PAPERSAGE_MAX_DELEGATED_TASKS_PER_RUN` env override that caps every
  pack's budget.
- [ ] Test scenario resolution (mode → pack), invalid-pack fail-fast, and env
  override precedence.

## 2. Layered output contracts

- [ ] Implement the contract registry: dotted-path resolution of Pydantic
  models declared by packs; no static scenario imports in runtime modules.
- [ ] Define the generic minimal contract `freeform_v1` with layered
  semantics: hard checks only for machine-consumed fields (parseable source
  references when present, runtime-injected provenance); narrative fields
  loosely bounded (non-empty summary, length caps).
- [ ] Add the `output_contract` front-matter field to `agent.md` and wire it
  through the loader.
- [ ] Validate child results at the layered boundary in the subagent task
  executor: at most one repair retry with the validation error fed back; a
  still-violating output is persisted and delivered as a `contract_violation`
  envelope (raw output + reason), and the task completes normally.
- [ ] Make the continuation ToolMessage carry either the validated payload or
  the violation envelope (keep the `packet` key shape); unmarked free-text
  handoff must never reach a parent continuation.
- [ ] Provide a pack-registerable final-output validation point on the Leader
  answer path (one bounded revision round; still-failing answers finalize with
  a visible validator marker). Research's citation-scope rule registers here
  in the follow-up pack change.
- [ ] Test the contract-valid path, the violation-envelope path (task
  completes, marker present, sibling tasks unaffected), the single repair
  retry, the final-output validation point, and that provenance is
  runtime-injected (model cannot forge it).

## 3. Delegation specification

- [ ] Extend `DelegateTaskInput` with optional `output_format` and `boundaries`;
  persist them with the task input and inject them into the child system prompt.
- [ ] Rewrite the delegation system prompt as a teaching checklist
  (objective / output format / boundaries / role contract summary) and echo the
  role's contract summary in the tool result so the Leader knows the expected
  payload shape.
- [ ] Neutralize research-specific wording in `DurableDelegationMiddleware`
  prompts, docstrings and tool descriptions.
- [ ] Test that delegations with and without optional spec fields both succeed
  and that spec fields appear in the persisted task input.

## 4. Run-level delegation budget

- [ ] Enforce the per-run max delegated tasks count inside the
  `submit_delegated_agent_task` transaction (count existing `kind='subagent'`
  tasks of the run); over-budget returns `budget_exceeded` with limit, current
  count and replan guidance, creating no task and raising no exception.
- [ ] Extend the baseline metrics repository with delegation budget
  utilization and contract violation counts (with reason distribution).
- [ ] Test the boundary (N-th allowed, N+1-th rejected), that the run continues
  after `budget_exceeded`, and metric recording.

## 5. Per-role model routing

- [ ] Wire the `model` field from role definitions into child task execution
  (reuse the user's provider/base_url/api key); undeclared roles inherit the
  Leader model.
- [ ] Record the actually-used model name on the attempt; extend baseline
  metrics with per-role model usage distribution.
- [ ] Test declared-model execution, inheritance, and attempt attribution.

## 6. Concurrency, evals and regression

- [ ] Two concurrent same-role children with contracts complete independently;
  each continuation payload maps to its own `task_uid`.
- [ ] A contract violation envelope from one child does not poison the
  sibling's continuation.
- [ ] Add eval coverage: contract violation rate and budget utilization across
  the existing eval scenarios; keep end-state scoring semantics.
- [ ] Add the acceptance scenario: a fixture pack (two roles, generic contract)
  delegates end-to-end with zero runtime code changes.
- [ ] Keep `tests/integration/test_run_path_baseline.py` and the whole existing
  run-path baseline green.

## 7. Docs and relationship cleanup

- [ ] Update `docs/architecture/durable-runtime-baseline.md` (pack layout,
  contracts, budget, routing, metrics) and the architecture docs referenced by
  README.
- [ ] Confirm the supersession note in `durable-research-agent-runtime`
  tasks §7 points to `research-scenario-pack` (built on this change).
- [ ] Run `bash scripts/quality_gate.sh core`, focused unit/integration suites,
  and update AGENTS.md-referenced test commands if paths changed.

## Exit criteria

- [ ] A new scenario pack (fixture) can be added under `agent/scenarios/` with
  roles, prompt, budget and contracts, and delegates end-to-end without any
  change to `agent/application`, `agent/middlewares` or `agent/adapters`.
- [ ] Every delegated child result that reaches a parent continuation is
  either contract-valid or explicitly marked as a contract violation with its
  reason; unmarked free-text handoff no longer exists on the delegated path.
- [ ] Delegation budget is enforced transactionally and observable in baseline
  metrics; `budget_exceeded` never fails the run.
- [ ] Per-role model routing is active, auditable on attempts, and defaults to
  inheritance.
- [ ] `DURABLE_AGENT_TASKS_ENABLED=false` disables all of the above for new
  runs without breaking existing history or the direct-answer path.
