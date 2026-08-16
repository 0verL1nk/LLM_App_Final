# Implementation Tasks

## 1. Backend

- [ ] Extend the memory repository with user-facing list (paginated, type
  filter, keyword search), create (source=user_managed), optimistic-locked
  update (409 on stale) and idempotent delete.
- [ ] Add project memory CRUD routes with ownership checks, reusing the
  existing memory data model — no second store.
- [ ] Test: deleted entries are excluded from injection immediately and the
  consolidator never resurrects them; system updates keep the
  user-modified marker.

## 2. Management UI

- [ ] Build the project memory panel: grouped list by memory type with
  counts, type filter, keyword search, pagination; create/edit/delete with
  confirmation and conflict (409) handling.
- [ ] Mark user-managed entries and "modified since manual edit" distinctly;
  show provenance when recorded, "系统整理" otherwise — never fabricated.
- [ ] Link inspector "已使用的长期记忆" entries to the panel locating the
  same item.

## 3. Tests and docs

- [ ] API tests (auth, pagination, optimistic lock, idempotent delete) and
  UI tests (render, filter/search, conflict, cross-link).
- [ ] Update README two-layer memory wording; run
  `bash scripts/quality_gate.sh core`, `pnpm --dir web test`,
  `pnpm --dir web typecheck`.

## Exit criteria

- [ ] A user can see every long-term memory item of a project, correct a
  wrong one, remove an unwanted one, and add a preference — all reflected in
  the next run's injected context.
- [ ] System consolidation and user management coexist without resurrection
  of deleted items and with visible provenance honesty.
