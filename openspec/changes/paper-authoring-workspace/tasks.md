# Implementation tasks

## 1. Contracts and persistence

- [ ] Define typed `PaperDraft`, source file manifest, `DraftRevision`, `CompileAttempt`,
  `CompileArtifact`, normalized diagnostic and claim-span provenance contracts in
  `agent/domain`.
- [ ] Add ownership-aware SQLite adapters and migration tests; revisions are append-only
  and source writes require `base_revision_uid` compare-and-set.
- [ ] Define FastAPI routes for draft read/write, revision proposal/review, compile
  enqueue/status and owner-only artifact download.

## 2. Safe local compilation

- [ ] Add a compiler capability probe that reports installed trusted engine availability
  without claiming a compile is possible when it is not.
- [ ] Implement adapter-owned staging, command allowlist, resource limits, bounded
  diagnostics and atomic PDF artifact publish.
- [ ] Run compilation through a lease/outbox worker and add crash, timeout, malformed
  diagnostic and previous-artifact preservation tests.

## 3. Authoring workspace UI

- [ ] Add a project-scoped paper workspace route and empty state linked from project
  navigation; do not replace existing research sessions until the route is usable.
- [ ] Integrate a maintained source editor component and PDF viewer with a responsive
  split-pane/tab layout.
- [ ] Render only server-backed draft contents, compile artifacts and diagnostics;
  add loading/error/unsupported-engine states without mock PDF or progress.
- [ ] Add source/PDF/diagnostic navigation and accessibility coverage for keyboard and
  narrow-window layouts.

## 4. AI collaboration and evidence

- [ ] Pass explicit `draft_uid`, file and selected span into writing requests; preserve
  ordinary research conversations when no draft context is selected.
- [ ] Store model edits as reviewable revisions/diffs with evidence provenance; accept,
  reject and rollback are server mutations.
- [ ] Dock the existing AI Elements conversation below the authoring canvas and offer a
  resizable floating panel; retain the live Run/SteeringInput queue semantics.
- [ ] Add tests for no silent overwrite, stale revision conflict, unsupported factual
  claim, source-to-evidence navigation and PDF artifact refresh after compile.

## 5. Desktop connection and account area

- [ ] Design authenticated remote API capability/version negotiation and secure token
  storage before adding cloud transport.
- [ ] Add an Electron main/preload connection-state contract; place the account and
  local/cloud selector in the left sidebar footer.
- [ ] Enable remote selection only after authenticated compatibility succeeds; invalidate
  caches/SSE safely on switch and show a concrete connection error on failure.

## 6. Documentation and acceptance

- [ ] Update desktop/web/agent architecture documents and a compile safety runbook.
- [ ] Add API/repository/worker unit tests, UI tests and one desktop end-to-end flow:
  save source → compile → view PDF → request AI change → review → accept → recompile.
- [ ] Run focused Python tests, `pnpm --dir web test`, `pnpm --dir web typecheck`,
  `git diff --check`, and platform-specific desktop packaging checks.
