## ADDED Requirements

### Requirement: Feedback Signal Capture

The system SHALL capture user correction signals from research sessions as structured, idempotent feedback events, using deterministic rules only.

#### Scenario: Correction follow-up detected

- **WHEN** a steering input arrives shortly after an answer and matches the correction similarity or leading-word rules
- **THEN** a correction_followup feedback event is recorded with the run and prompt digest
- **AND** recapture of the same signal is deduplicated by its idempotency key

#### Scenario: Mode-switch re-ask detected

- **WHEN** two adjacent turns in a session share a highly similar prompt but differ in requested execution mode
- **THEN** a mode_switch_reask event is recorded

#### Scenario: Insufficient data skips the signal

- **WHEN** the data needed to evaluate a rule is missing
- **THEN** no event is recorded and nothing is guessed

### Requirement: Finding Aggregation

The system SHALL aggregate feedback events into findings so recurring patterns are distinguishable from one-off noise.

#### Scenario: Recurring correction becomes a finding

- **WHEN** the same signal type recurs at least the configured minimum within a project
- **THEN** the finding appears in the findings list with its count, latest sample, and related documents

#### Scenario: One-off signals stay out

- **WHEN** a signal occurs only once
- **THEN** it does not appear as a finding

### Requirement: Operator-Reviewed Case Export

The system SHALL let an operator turn a finding into an eval case draft without automatic fixture mutation.

#### Scenario: Export a case draft

- **WHEN** the operator exports a finding
- **THEN** the response contains a JSONL case draft with the original user question, a signal-type-specific rubric skeleton, and origin metadata tracing back to the finding

#### Scenario: No automatic fixture writes

- **WHEN** a draft is exported
- **THEN** eval fixture files are not modified; merging the draft is an explicit operator action
