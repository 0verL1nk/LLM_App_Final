# ORM persistence foundation

## Why

PaperSage currently uses many independent `sqlite3` repositories. Parameter binding
protects most value inputs today, but schema creation, transaction control, ownership
joins and dynamic query fragments are repeated manually. The durable Run/Task/Input
work should not continue creating a second long-lived persistence style.

## What Changes

1. Adopt SQLAlchemy 2.x as a direct dependency and Alembic for versioned migrations.
2. Introduce one database engine/session boundary and typed ORM models for new durable
   runtime tables first: Run, RunEvent, RunItem, Task, TaskAttempt, TaskOutbox and
   SteeringInput.
3. Replace raw dynamic SQL with expression APIs; raw SQL remains permitted only for
   SQLite pragmas or verified migration DDL, never constructed from request input.
4. Migrate existing project/session tables incrementally behind repository contracts;
   no big-bang rewrite and no dual authoritative write path.

## Non-goals

- Do not rewrite all legacy document/OCR storage in one change.
- Do not claim ORM alone solves authorization: repositories must still scope every
  project/session/run read and mutation by owner.
- Do not use `create_all` as production migration management.

## Impact

- Backend dependency, migration tooling, database lifecycle and repository tests.
- Durable runtime repositories are the first migration wave because they are actively
  changing and contain transactional queue/lease semantics.
- Desktop packaging must include migration execution before starting the API.
