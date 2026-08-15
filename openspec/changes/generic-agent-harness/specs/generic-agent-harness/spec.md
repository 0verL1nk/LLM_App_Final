## ADDED Requirements

### Requirement: Scenario pack instantiation

The system SHALL resolve an execution mode to a declarative scenario pack that
provides roles, the Leader prompt, delegation budget defaults and output
contracts. Adding a scenario pack SHALL NOT require changes to
`agent/application`, `agent/middlewares` or `agent/adapters` modules.

#### Scenario: Adding a scenario without runtime changes

- **WHEN** a new pack directory with a valid manifest, roles and contracts is
  added under `agent/scenarios/` and its execution mode is selected
- **THEN** the runtime delegates to the pack's roles, enforces the pack's
  budget and validates against the pack's contracts without any runtime code
  edit

#### Scenario: Invalid pack fails fast

- **WHEN** a pack manifest references an unknown contract, duplicates a role
  name or declares a non-positive budget
- **THEN** session construction fails with an explicit error
- **AND** the system does not silently fall back to another pack or to
  contract-less execution

### Requirement: Layered output contracts

Every delegatable role SHALL declare an output contract. Contracts SHALL
enforce machine-consumed fields strictly (parseable source references and
runtime-injected provenance) while keeping narrative fields loosely bounded.
A contract violation SHALL NOT terminate the task: after at most one repair
retry, the raw output SHALL be delivered to the parent continuation inside an
explicit `contract_violation` envelope carrying the violation reason.

#### Scenario: Contract-valid child result

- **WHEN** a delegated child completes with output satisfying its role contract
- **THEN** the validated payload is persisted with the task result
- **AND** the parent continuation ToolMessage carries that structured payload

#### Scenario: Contract violation degrades gracefully

- **WHEN** a delegated child completes with output violating the
  machine-consumed field constraints after the repair retry
- **THEN** the task still completes and its result is wrapped in a
  `contract_violation` envelope carrying the violation reason
- **AND** the parent continuation receives the envelope with an explicit
  violation marker instead of an unmarked free-text handoff
- **AND** the violation is counted in baseline metrics

#### Scenario: Unforgeable provenance

- **WHEN** any child payload is delivered to a continuation or audit surface
- **THEN** its provenance (task, role, attempt) is populated by the runtime
  and cannot be authored by the child model

### Requirement: Final-output validation hook

The harness SHALL provide a pack-registerable validation point on the Leader's
final answer. A validator MAY reject an answer with a reason; a rejection
SHALL trigger at most one revision round, and an answer that still fails SHALL
be finalized with a visible validator marker rather than silently published.

#### Scenario: Pack registers a citation-scope validator

- **WHEN** a pack registers a final-output validator and the Leader's final
  answer violates it
- **THEN** the Leader receives the rejection reason and produces one revision
- **AND** a still-failing answer is finalized with the validator marker visible

### Requirement: Delegation specification completeness

The `delegate_task` input SHALL accept an objective plus optional
`output_format` and `boundaries` fields, persist them with the task input, and
inject them into the child system prompt. The delegation guidance SHALL teach
the objective / output format / boundaries checklist and surface each role's
contract summary to the Leader.

#### Scenario: Delegation with explicit specification

- **WHEN** the Leader delegates with `output_format` and `boundaries` set
- **THEN** the persisted task input records both fields
- **AND** the child system prompt includes them

#### Scenario: Leader learns the expected payload shape

- **WHEN** the Leader lists or invokes delegation roles
- **THEN** the tool surface presents each role's contract summary so the
  Leader knows the shape of the expected result

### Requirement: Run-level delegation budget

The system SHALL enforce a per-run maximum number of delegated child tasks,
defaulted by the scenario pack and overridable by environment. Enforcement
SHALL be transactional with task creation.

#### Scenario: Budget exceeded

- **WHEN** the Leader submits a delegation beyond the run's budget
- **THEN** `delegate_task` returns a `budget_exceeded` result with the limit,
  the current count and replan guidance
- **AND** no task is created and the run does not fail

#### Scenario: Budget observability

- **WHEN** baseline metrics are collected
- **THEN** delegation budget utilization and contract violation counts are
  reported per run

### Requirement: Per-role model routing

Role definitions MAY declare a model; the child executor SHALL execute with
the declared model and SHALL record the actually-used model on the attempt.
Roles without a declaration SHALL inherit the Leader's model.

#### Scenario: Declared role model

- **WHEN** a role with a declared model is delegated
- **THEN** the child executes with that model using the user's provider
  configuration
- **AND** the attempt records the model name used

#### Scenario: Model inheritance

- **WHEN** a role without a declared model is delegated
- **THEN** the child executes with the Leader's model and the attempt records
  it

### Requirement: Runtime-scenario boundary

Runtime modules SHALL NOT import scenario pack content directly; contracts
SHALL resolve exclusively through the registry. The architecture boundary
test SHALL reject violations and the retired `agent/subagent/` path SHALL NOT
return.

#### Scenario: Architecture test rejects a scenario import

- **WHEN** a module under `agent/application`, `agent/middlewares` or
  `agent/adapters` imports `agent.scenarios.*` or statically imports a
  scenario contract class
- **THEN** the architecture boundary test fails the build
