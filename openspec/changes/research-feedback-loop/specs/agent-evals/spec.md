## MODIFIED Requirements

### Requirement: Structured Eval Case Schema

The system SHALL support a structured eval fixture schema for defining prompts, categories, expected outcomes, and process constraints.

#### Scenario: Valid eval case fields

- **WHEN** the system loads an eval fixture row
- **THEN** it validates that the row contains a stable case identifier, a prompt, and the fields required by the selected scoring mode

#### Scenario: Retrieval-oriented constraints

- **WHEN** an eval case requires grounded retrieval behavior
- **THEN** the fixture schema can declare constraints such as minimum evidence count or evidence-required completion

#### Scenario: Multi-step task constraints

- **WHEN** an eval case requires planning or task tracking behavior
- **THEN** the fixture schema can declare constraints such as required plan usage, todo completion expectations, or trajectory hints
- **AND** those constraints MUST be expressed in terms of stable normalized outputs rather than middleware-private implementation details

#### Scenario: Production provenance metadata

- **WHEN** a fixture row carries `origin: production-finding` with finding traceability fields
- **THEN** the loader preserves them as case metadata without requiring any contract change for self-authored rows
- **AND** cases without an origin marker continue to load unchanged

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

#### Scenario: Origin-layered completion rates

- **WHEN** a report is generated over a fixture that mixes self-authored and production-finding cases
- **THEN** the report layers completion rates by case origin so production-sourced coverage is distinguishable from self-authored coverage
