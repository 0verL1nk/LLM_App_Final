## ADDED Requirements

### Requirement: Provider Circuit Breaker

The web search provider chain SHALL skip a provider that fails repeatedly within the running process, and SHALL recover it through half-open probing.

#### Scenario: Consecutive failures trip the breaker

- **WHEN** a provider fails PROVIDER_CIRCUIT_FAILURE_THRESHOLD consecutive times
- **THEN** subsequent queries skip that provider until its cooldown expires
- **AND** the state transition is logged once, not per skipped query

#### Scenario: Half-open recovery

- **WHEN** a cooldown expires and the next query reaches the provider
- **THEN** success resets the failure counter and closes the breaker
- **AND** failure doubles the next cooldown up to the configured maximum

### Requirement: Frozen Web Fixtures For Evals

Eval runs SHALL support replaying web search results from versioned fixtures so web-dependent cases are deterministic across runs.

#### Scenario: Replay hit

- **WHEN** an eval run in replay mode issues a web query present in the fixture
- **THEN** the tool returns the recorded result without touching live providers

#### Scenario: Replay miss is explicit

- **WHEN** a web query is absent from the fixture in replay mode
- **THEN** the case fails with a web_fixture_miss marker instead of silently falling back to live search

#### Scenario: Recording and refreshing

- **WHEN** an operator runs with record mode (optionally refresh)
- **THEN** live results for each query are written into the fixture with a capture date
- **AND** the report's run provenance records the fixture name and checksum

### Requirement: Judge Independence Comparison

The eval tooling SHALL support comparing verdicts between the agent's model and an independent judge model, reporting per-case agreement.

#### Scenario: Comparison run

- **WHEN** an operator runs the judge comparison flow with an independent judge model
- **THEN** the report lists per-case agree/disagree verdicts and an overall agreement rate
- **AND** the comparison does not alter the canonical scoring path
