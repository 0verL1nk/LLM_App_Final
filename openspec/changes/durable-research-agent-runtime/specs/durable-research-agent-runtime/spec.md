## ADDED Requirements

### Requirement: Durable task identity

The system SHALL persist every delegated agent task as an open-kind `AgentTask` with a
stable `task_uid`, owning `run_uid`, parent relation, role, status, idempotency key
and auditable attempts.

#### Scenario: Same-role concurrent delegation

- **WHEN** a Leader delegates two independent tasks to the same role with the same
  human-readable description
- **THEN** the system creates two distinct `task_uid` values
- **AND** each lifecycle event, result, retry and UI item remains associated with its
  own task

#### Scenario: Duplicate task submission

- **WHEN** a dispatcher receives the same idempotent delegation request more than once
- **THEN** it returns the existing task without creating a duplicate attempt or
  duplicate parent continuation

### Requirement: Leader Run dispatch uses the unified task lifecycle

The system SHALL represent each executable Run as one top-level `LEADER` task and
dispatch it through the same durable task outbox used by child and continuation work.
The API process SHALL NOT be the Run execution owner.

#### Scenario: Duplicate multi-instance delivery

- **WHEN** two worker instances receive delivery for the same leader task
- **THEN** exactly one database lease owner executes the model turn
- **AND THEN** the other instance records no competing Run terminal state

### Requirement: Lease-based execution recovery

The system SHALL claim task attempts through durable leases and reconcile abandoned
work after worker interruption.

#### Scenario: Worker terminates during child execution

- **WHEN** a worker lease expires without completion
- **THEN** the reconciler records the expired attempt and makes the task retryable
- **AND** a late completion from the expired attempt cannot overwrite a newer attempt

### Requirement: Typed item lifecycle

The system SHALL emit ordered, versioned item events for all user-observable Agent
work and SHALL treat the terminal item event as authoritative.

#### Scenario: Tool execution streams

- **WHEN** a research tool starts, produces incremental output and completes
- **THEN** the event stream emits one item creation, zero or more deltas, and exactly
  one terminal completion or failure for the same item ID

#### Scenario: Browser reconnects

- **WHEN** a browser reconnects with its last applied sequence
- **THEN** the server replays only later events in order
- **AND** the client can reconstruct the same item state without duplicate text,
  task cards or tool results

### Requirement: Unified plan and task state

The system SHALL represent a plan as typed steps and SHALL link delegated work to
plan steps where applicable.

#### Scenario: Child task starts and completes

- **WHEN** a task linked to a plan step is claimed
- **THEN** the runtime marks that step `in_progress`
- **WHEN** the task reaches a terminal state
- **THEN** the runtime marks the linked step with the corresponding terminal status

#### Scenario: Simple answer requires no plan

- **WHEN** the Leader answers a straightforward research question without creating a
  plan
- **THEN** the run succeeds without a synthetic plan or Todo item

### Requirement: Durable parent continuation

The system SHALL resume a parent Agent exactly once after required joined children
reach terminal states.

#### Scenario: Concurrent child completion

- **WHEN** the final two required children complete nearly simultaneously
- **THEN** the system creates at most one continuation task for the parent epoch
- **AND** the resumed Leader receives only validated child ToolMessage results

#### Scenario: Child fails

- **WHEN** a required child fails
- **THEN** the parent continuation receives a structured failure result
- **AND** the Leader may replan, retry through an explicit tool call, or produce a
  bounded partial answer

### Requirement: Cancellation and ownership

The system SHALL expose idempotent cancellation and retry operations only to the
owner of the corresponding project/session.

#### Scenario: User cancels an active run

- **WHEN** the owning user cancels a Run with active children
- **THEN** the runtime records cancellation, signals active task workers at a safe
  boundary, terminates pending descendants, and emits durable terminal events

#### Scenario: Unauthorized task access

- **WHEN** a requestor does not own the task's project/session
- **THEN** the system rejects inspect, input, retry and cancel operations without
  revealing task metadata

### Requirement: Evidence-safe child results

The system SHALL validate evidence references returned by child tasks before making
them available to the Leader or final citation renderer.

#### Scenario: Child returns fabricated evidence ID

- **WHEN** a child result references an ID absent from the current project evidence
  scope
- **THEN** the runtime drops that reference, records a validation failure, and does
  not present it as a source to the user

### Requirement: Evidence-packet collaboration

The system SHALL require research-oriented child tasks to return a validated
`EvidencePacket` containing atomic claims, evidence references, limitations and
open questions. Role labels alone SHALL NOT be treated as proof of research quality.

#### Scenario: Research task returns a supported paper fact

- **WHEN** an evidence research task asserts a fact from a project document
- **THEN** the packet includes a valid local evidence reference with its available
  document/page/coordinate provenance
- **AND** the Leader can reuse that reference in a final answer or writing revision

#### Scenario: Research task reaches an unresolved conclusion

- **WHEN** available sources do not establish the requested conclusion
- **THEN** the packet records an open question or limitation
- **AND** the final answer does not upgrade it into a confirmed paper fact

### Requirement: Conflict-preserving synthesis

The system SHALL preserve supported contradictory claims across subagent outputs
until the Leader explicitly resolves them with evidence.

#### Scenario: Two papers report incompatible findings

- **WHEN** independently completed EvidencePackets support incompatible findings
- **THEN** the merger retains both claims and their evidence references
- **AND** it exposes the conflict to the Leader and research UI instead of selecting
  a majority or silently discarding one claim

### Requirement: Provenance-aware writing revision

The system SHALL model generated writing as a non-destructive revision with
claim-to-evidence provenance.

#### Scenario: Draft contains a source-grounded factual sentence

- **WHEN** the writing Agent emits a factual claim based on a validated packet
- **THEN** the DraftRevision associates its claim span with the corresponding
  evidence references
- **AND** the UI can open the original source location from that span

#### Scenario: Draft contains an unsupported synthesis

- **WHEN** a draft claim lacks sufficient packet evidence
- **THEN** the revision reports it as an unsupported claim or citation gap
- **AND** it is not rendered with a false source citation

### Requirement: Research-state memory provenance

The system SHALL persist durable research artifacts with source run/task/evidence
provenance and SHALL not treat a free-form conversation summary as sole factual
grounding.

#### Scenario: Later session reuses a prior project conclusion

- **WHEN** a later research session retrieves a stored conclusion artifact
- **THEN** it receives the artifact's source task/run and evidence references
- **AND** the Agent can verify that the referenced evidence remains within the
  current project scope before relying on it
