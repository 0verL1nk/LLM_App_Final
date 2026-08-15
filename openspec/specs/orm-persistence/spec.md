# orm-persistence Specification

## Purpose
TBD - created by archiving change orm-persistence-foundation. Update Purpose after archive.
## Requirements
### Requirement: Durable runtime persistence uses ORM models and versioned migrations

The system SHALL manage durable Run, Task and SteeringInput tables through SQLAlchemy
models and Alembic migrations. Production startup SHALL run compatible migrations before
serving work.

#### Scenario: Existing local database upgrade

- **WHEN** a desktop application opens an existing supported SQLite database
- **THEN** migrations upgrade it transactionally to the current runtime schema
- **AND THEN** existing projects, sessions and readable Run history remain intact

### Requirement: Repository mutation is parameter-safe and owner-scoped

The system SHALL express request-derived predicates through ORM bound parameters and
shall scope user-visible reads/mutations by the requesting owner's project/session.

#### Scenario: Foreign user requests a Run

- **WHEN** a request targets a Run owned by another user
- **THEN** the repository returns no record to the application route
- **AND THEN** the route does not reveal task, input or event metadata

### Requirement: Lease and queue transitions remain atomic

The ORM migration SHALL preserve compare-and-set semantics for Run claims, task leases
and steering-input transfers.

#### Scenario: Duplicate worker dispatch

- **WHEN** two workers attempt to claim the same queued Run
- **THEN** exactly one transaction changes it to running
- **AND THEN** the other worker performs no model execution

