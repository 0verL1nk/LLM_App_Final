# Design: paper authoring workspace

## Product hierarchy

```text
Project
└─ PaperDraft
   ├─ DraftRevision (immutable, reviewable proposal or accepted save)
   ├─ LaTeX source tree (canonical editable files)
   ├─ CompileAttempt (lease-backed, bounded worker execution)
   │  ├─ PDF artifact
   │  └─ diagnostics + SyncTeX/source map when available
   └─ ResearchSession / Run (AI collaboration, evidence and task history)
```

`PaperDraft` is not a chat transcript. `ResearchSession` remains reusable for research,
but a writing action includes `draft_uid`, target file/span and expected revision base.

## Layout and interaction

On desktop, the editor and rendered PDF are equally primary, separated by a draggable
split pane. The PDF pane never renders an optimistic result: it shows the latest
successfully compiled artifact, or the latest server diagnostic state. The AI panel is
collapsed by default after a user opens a draft; it docks below the two-pane canvas and
can be expanded into a resizable right-side sheet. On narrow widths, editor/PDF are tabs
and the AI panel is a bottom sheet.

The panel receives the active source selection and evidence context explicitly. A model
proposal is stored as a `DraftRevision` with unified diff, provenance and diagnostics
against `base_revision_uid`; accept is an optimistic-concurrency server mutation. The
editor updates only after that mutation succeeds.

## Compilation safety

Compilation is an adapter-owned, lease-backed worker job, separate from the Agent tool
loop. It runs only a project-owned staging tree, has a bounded command allowlist,
no shell interpolation, restricted environment/network and output-size/time limits.
Artifacts are published atomically: a failed attempt preserves the previous successful
PDF. The first local implementation should use an installed trusted TeX distribution;
cloud compilation must run in isolated infrastructure and have its own security spec.

The worker persists `CompileAttempt` rather than emitting in-memory process progress.
It publishes normalized diagnostics (file, line, column, severity, safe message) and
an artifact checksum. Raw compiler output is retained only as bounded diagnostics for
the owner, never streamed into the model prompt by default.

## Evidence and source navigation

Each factual changed span carries `ClaimProvenance` pointing to evidence IDs already
validated by the research runtime. A UI click resolves an editor position/PDF mapping
to the revision span, then opens the existing evidence inspector. Missing provenance is
displayed as a citation gap, not an invented reference. SyncTeX is optional: compile
success must not depend on it, and navigation falls back to file/line source spans.

## Desktop connection boundary

The renderer reads an opaque connection state from the existing preload platform
boundary. Electron main process owns persistent endpoint selection and any credentials
through OS-backed secure storage. Local mode targets the packaged FastAPI service.
Remote mode requires a versioned authenticated API capability document and must use a
real account/session token, never the current development `X-User-Id: local-user`
convention. Switching target clears/invalidate TanStack Query caches and re-establishes
SSE; it does not migrate local projects automatically.

## Rollout

1. Land contracts, storage, empty-state route and real compile capability probe.
2. Land source editing/revisions with a single trusted local compiler.
3. Land PDF/artifact viewer and diagnostics/source navigation.
4. Bind AI writing suggestions to revisions and evidence provenance.
5. Add connection selector only once remote auth/capability checks exist.
