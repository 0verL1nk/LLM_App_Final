## ADDED Requirements

### Requirement: Tiered Evidence Injection

When enabled, document search SHALL deliver evidence previews with intact citation fields and provide on-demand full-text retrieval per session.

#### Scenario: Preview shaping

- **WHEN** tiering is enabled and an evidence chunk exceeds the preview budget
- **THEN** the payload carries a truncated text with truncated=True while chunk_id, doc_uid, and page fields remain intact
- **AND** the payload carries a hint pointing to the read_evidence expansion path

#### Scenario: On-demand full text

- **WHEN** the model calls read_evidence with a chunk_id truncated by a tiered search
- **THEN** the full original text is returned

#### Scenario: Session isolation

- **WHEN** two sessions exist concurrently
- **THEN** each session's read_evidence cache contains only chunks truncated within that session

#### Scenario: Default unchanged

- **WHEN** AGENT_EVIDENCE_TIERED is not enabled
- **THEN** search payloads carry full text and the read_evidence tool is not registered

### Requirement: Citation Audit Signal

The turn engine SHALL deterministically annotate each turn with a citation audit verdict.

#### Scenario: Failed audit

- **WHEN** evidence items were retrieved but the final answer cites none of them
- **THEN** the turn result carries citation_audit=failed with a warning log

#### Scenario: Not applicable

- **WHEN** no evidence was retrieved
- **THEN** the verdict is not_applicable
