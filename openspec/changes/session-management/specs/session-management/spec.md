## ADDED Requirements

### Requirement: Session renaming

The system SHALL allow renaming the main session and exploration branches;
the new title SHALL propagate to the session list and document title, SHALL
create no new session record, and SHALL not be overwritten by the automatic
title generator once set by the user.

#### Scenario: Rename an exploration branch

- **WHEN** a user renames a branch
- **THEN** the research-thread list and page title show the new name
- **AND** the session identity (session_uid) and history are unchanged
- **AND** the async title generator no longer overwrites the user title

### Requirement: Exploration branch deletion

The system SHALL support deleting exploration branches with confirmation,
idempotency and ownership checks; deleted branches SHALL disappear from all
session views while run event history remains readable, and the main session
SHALL be protected from deletion.

#### Scenario: Delete a branch

- **WHEN** a user confirms deletion of an exploration branch
- **THEN** the branch and its messages no longer appear in any session list
- **AND** repeating the delete succeeds idempotently

#### Scenario: Main session is protected

- **WHEN** deletion is requested for the main session
- **THEN** the server rejects it with an explicit protected error and the UI
  offers no delete affordance for it
