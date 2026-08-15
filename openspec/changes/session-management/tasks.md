# Implementation Tasks

- [ ] Add session title update (validate non-empty, trim, cap 120; mark
  `title_source=user`) and branch soft-delete (`deleted_at`, filtered from
  all list/message queries) to the project repository.
- [ ] Make the async session-title generator skip user-titled sessions.
- [ ] Add `PATCH /projects/{p}/sessions/{s}` and `DELETE ...` routes with
  ownership checks, idempotent delete, and `409 main_session_protected` for
  the main session.
- [ ] Session list UI: inline rename and delete actions with confirmation
  showing message count; navigate to the main thread when deleting the open
  branch; no delete affordance on the main session.
- [ ] Tests: rename propagation and no-auto-overwrite, delete cascade view
  filtering, idempotency, main-session protection, ownership, navigation.
- [ ] Update README 研究脉络 wording; run `bash scripts/quality_gate.sh core`,
  `pnpm --dir web test`, `pnpm --dir web typecheck`.

## Exit criteria

- [ ] Users can rename any session and delete exploration branches with
  confirmed, idempotent semantics; the main thread is protected.
- [ ] Deleted branches disappear from all session views while run event
  history remains intact, and manual titles are never overwritten by the
  automatic generator.
