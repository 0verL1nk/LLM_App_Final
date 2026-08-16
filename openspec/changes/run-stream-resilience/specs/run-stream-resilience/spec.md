## ADDED Requirements

### Requirement: Automatic run stream resumption

When an in-progress run stream ends abnormally, the client SHALL automatically
reconnect using `afterSeq` with the last applied sequence, preserving ordered,
deduplicated rendering, and SHALL stop reconnecting once the run reaches a
terminal state.

#### Scenario: Mid-stream drop resumes automatically

- **WHEN** the SSE stream of an in-progress run errors or closes early
- **THEN** the client reconnects with `afterSeq` set to the last applied
  sequence using exponential backoff
- **AND** replayed events render once, in order, with no duplicated content

#### Scenario: Terminal run stops retrying

- **WHEN** a terminal run event or polled terminal status is observed
- **THEN** the client stops all reconnection attempts regardless of state

### Requirement: Bounded degradation to polling

The client SHALL cap SSE reconnection attempts (default 10) and SHALL fall
back to the existing polling recovery path for in-progress runs, surfacing
the degradation honestly.

#### Scenario: Sustained failure degrades to polling

- **WHEN** reconnection attempts reach the cap while the run is still in
  progress
- **THEN** the client switches to polling-based recovery
- **AND** a visible status indicates the degraded mode without fabricated
  progress

### Requirement: Visibility-triggered recovery

When the page becomes visible while recovery is pending, the client SHALL
trigger an immediate recovery attempt without waiting for the remaining
backoff delay.

#### Scenario: Return to a backgrounded tab

- **WHEN** the tab becomes visible while in reconnecting or polling state for
  an in-progress run
- **THEN** an immediate recovery attempt starts at once
