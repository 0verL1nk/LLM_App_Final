# Implementation Tasks

- [ ] Verify run detail/event serialization exposes the persisted
  `ExecutionRoute` (requested/resolved/reason); add the field if missing —
  no second storage.
- [ ] Add the mode badge to assistant messages: explicit choice, auto-resolved
  (Auto → X with reason on hover), and fallback warning style.
- [ ] Add the full routing record section to the run inspector; show "无记录"
  for legacy runs without data.
- [ ] Maintain the reason-code → Chinese copy mapping with raw-code fallback.
- [ ] Tests: badge and inspector rendering for explicit/auto/fallback,
  missing-record omission, unknown reason code, history reload parity.
- [ ] Update README Agent design table; run `pnpm --dir web test`,
  `pnpm --dir web typecheck` and backend serialization tests.

## Exit criteria

- [ ] Every run with a persisted route shows requested mode, resolved mode
  and reason in both live and reloaded views, sourced from server facts.
- [ ] Runs without a route record show nothing rather than a guess, and
  invalid-override fallbacks are visually distinguishable.
