## ADDED Requirements

### Requirement: Live Runtime Baseline Execution

The system SHALL support executing eval cases against the live model runtime through the canonical turn execution path and persisting the resulting baseline artifact in the repository.

#### Scenario: Run a live baseline

- **WHEN** a developer runs the live eval command with model credentials configured
- **THEN** each selected case executes a real model-driven turn through the canonical turn execution path
- **AND** the run produces a report artifact under the committed baselines directory

#### Scenario: Live baseline provenance

- **WHEN** a baseline report is generated
- **THEN** the report records run provenance including runner mode, agent and judge model names, web-search fallback mode, and fixture path
- **AND** a reader can distinguish a live-system baseline from a scenario-calibration baseline without inspecting code

#### Scenario: Turn-level delegation measurement

- **WHEN** a live case declares delegation process contracts such as required subagent types or parallel delegation
- **THEN** the harness scores those contracts from the leader's emitted `delegate_task` tool calls
- **AND** turn-level delegation scoring does not require subagent tasks to execute within the harness

## MODIFIED Requirements

### Requirement: Task Completion Scoring

The system SHALL calculate task completion using both final-answer success and process-level success signals.

#### Scenario: Simple task completion

- **WHEN** an eval case only defines final-answer success criteria
- **THEN** the system determines completion from the final-answer evaluation result

#### Scenario: Process-constrained task completion

- **WHEN** an eval case defines process requirements such as minimum evidence, required planning, or expected multi-step completion
- **THEN** the system includes those process checks in the completion decision
- **AND** the case is not marked completed unless both final-answer and required process checks pass

#### Scenario: Execution completion ratio

- **WHEN** a turn result includes plan or todo completion data
- **THEN** the system computes an execution completion ratio for the case
- **AND** records that ratio in the case result and aggregate report

#### Scenario: Stable delegation tool contract

- **WHEN** a case declares required delegation tools or subagent roles
- **THEN** the contracts reference the canonical `delegate_task` tool with a `role` argument
- **AND** legacy `task` or `subagent_type` spellings do not satisfy delegation contracts

#### Scenario: Parallel delegation detection

- **WHEN** a case requires parallel delegation
- **THEN** the system detects at least two `delegate_task` calls within a single assistant message
- **AND** the parallel-delegation signal is derived from observed messages rather than a hardcoded constant

#### Scenario: Forbidden-tool contract

- **WHEN** a case declares tools that must not be used for its access mode (for example corpus-bound cases forbidding web search)
- **THEN** the system fails the process contract deterministically if any forbidden tool appears in the turn's used tools
- **AND** the case set keeps corpus-bound and web-bound cases balanced so routing discipline is measured in both directions

### Requirement: Itemized Judge Protocol

The system SHALL instruct the final-answer LLM judge to evaluate itemized rubric checks independently with quote-anchored justification.

#### Scenario: Item-by-item verdict

- **WHEN** the judge evaluates an answer against a rubric
- **THEN** each numbered rubric item is judged independently
- **AND** an item counts as satisfied only if a quotable span of the answer supports it

#### Scenario: Insufficient-information escape

- **WHEN** the transcript is genuinely insufficient to judge an item
- **THEN** the judge states so explicitly instead of guessing a verdict

#### Scenario: Judge model provenance

- **WHEN** a live eval run uses a judge model different from the agent model
- **THEN** both model names are recorded in the report's run provenance
- **AND** the live runner accepts explicit judge model overrides without changing the agent model

## MODIFIED Requirements

### Requirement: Eval Reports

The system SHALL generate machine-readable eval reports with both aggregate metrics and case-level diagnostics.

#### Scenario: Aggregate report generation

- **WHEN** an eval run completes
- **THEN** the system writes a report containing completion rate and other configured aggregate metrics

#### Scenario: Case-level diagnostics

- **WHEN** an eval report is generated
- **THEN** it includes per-case pass or fail data, scoring details, and enough context to identify why a case failed

#### Scenario: Existing router baseline remains separate

- **WHEN** developers run the new task-completion eval flow
- **THEN** the existing router baseline remains available as a separate routing-focused check
- **AND** the new eval report does not replace router metrics with route-only success

#### Scenario: Runner mode recorded

- **WHEN** a report is generated by either the scenario runner or the live runner
- **THEN** the report states which runner mode produced it as part of run provenance
- **AND** scenario-calibration results are not mistaken for live-system quality measurements
