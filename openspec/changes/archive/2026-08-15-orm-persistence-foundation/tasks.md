# Implementation tasks

- [x] Add direct SQLAlchemy 2.x and Alembic dependencies; create a single engine/session
  factory with SQLite foreign keys, busy timeout and transaction settings.
- [x] Create baseline Alembic revision from the deployed SQLite schema; add migration
  runner to API/desktop startup with rollback-safe failure reporting.
- [x] Define ORM models and constraints for agent runs, V2 events/items, tasks/attempts/
  outbox and steering inputs; include owner/project/session indexes and FK relationships.
- [x] Port the remaining task lifecycle repository, retaining its application-facing
  contracts and removing the old implementation once covered. Run events/items, task
  submission/outbox delivery, task lease/attempts, parent coordination and
  `steering_input_repository` are direct SQLAlchemy Core repositories in `agent/adapters/orm`.
- [x] Replace dynamic identifier interpolation with whitelisted ORM expressions; audit
  all remaining raw SQL and document each exception.
- [x] Add repository transaction/race tests for Run claim, event sequence allocation,
  task lease completion, steering transfer and owner isolation.
- [x] Update desktop/API architecture documentation and packaging checks; run the full
  focused runtime suite plus migration upgrade tests against an existing database copy.
