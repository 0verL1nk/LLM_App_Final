# Implementation Tasks

## 1. Reconnect state machine

- [ ] Implement a per-run stream connection state machine (live /
  reconnecting / polling / closed) with attempt counting, exponential
  backoff (1s ×2, cap 30s, ±20% jitter) and reset-on-success; terminal
  state detection from terminal events or polled run status only.
- [ ] On abnormal end before terminal, auto-reconnect SSE with
  `afterSeq = lastAppliedSequence`; rely on the existing reducer for
  dedupe/out-of-order buffering — no reducer changes.

## 2. Degradation and visibility

- [ ] After the attempt cap (default 10), stop SSE retries and switch to the
  existing polling recovery path while the run is in progress; periodically
  retry SSE from polling.
- [ ] On `visibilitychange → visible` during reconnecting/polling, trigger an
  immediate recovery attempt bypassing the remaining backoff wait.

## 3. Connection status UI

- [ ] Render a single connection status badge in the streaming area
  (实时/重连中·第 N 次/已切换轮询恢复/连接已断开) driven only by real
  connection facts; no fabricated progress.
- [ ] Reduce toasts to degraded-to-polling and final-failure notifications.

## 4. Tests and docs

- [ ] React tests: mid-stream error → auto-reconnect with correct afterSeq
  and no duplicate rendering; consecutive failures → polling fallback and
  recovery; terminal stops all retries; visibility-triggered resume; backoff
  jitter keeps counting correct.
- [ ] Update README "可恢复的研究过程" wording; run `pnpm --dir web test`,
  `pnpm --dir web typecheck`.

## Exit criteria

- [ ] A dropped SSE connection on an in-progress run resumes automatically
  with no user action, no duplicated content, and a visible honest status.
- [ ] Sustained failure degrades to polling instead of a dead-end toast, and
  terminal runs never trigger reconnection.
