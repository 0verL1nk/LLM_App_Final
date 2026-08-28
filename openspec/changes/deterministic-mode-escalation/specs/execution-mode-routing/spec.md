## ADDED Requirements

### Requirement: Structural Mode Routing

The system SHALL resolve execution modes from structural signals only, without keyword matching or prompt-length heuristics.

#### Scenario: Manual selection wins

- **WHEN** the requested mode is one of react, plan_execute, or agent_teams
- **THEN** that mode is used with an auditable user_selected reason

#### Scenario: Multi-document scope escalates to planning

- **WHEN** auto mode is requested and the project has at least MULTI_DOCUMENT_PLAN_THRESHOLD ready documents
- **THEN** the run resolves to plan_execute with a multi_document_scope reason

#### Scenario: Default stays bounded

- **WHEN** auto mode is requested and the document threshold is not met
- **THEN** the run resolves to react with a bounded_direct_request reason

#### Scenario: No keyword heuristics

- **WHEN** a prompt contains comparison or planning keywords
- **THEN** those keywords alone do not change the resolved mode

#### Scenario: Teams require explicit selection

- **WHEN** auto mode is requested
- **THEN** agent_teams is never auto-assigned
