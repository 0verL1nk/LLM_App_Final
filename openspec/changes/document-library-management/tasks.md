# Implementation Tasks

## 1. Backend lifecycle

- [ ] Add `update_document_title` and `delete_document` to the document
  repository with ownership checks; delete marks status terminal in one
  transaction and records derived-artifact cleanup as retryable steps.
- [ ] Implement derived-artifact purge (LanceDB chunks by doc_uid, page
  images, OCR artifacts, converted intermediates, original file) idempotently,
  with a startup/reconcile re-drive while cleanup is pending.
- [ ] Add `PATCH /documents/{doc_uid}` and `DELETE /documents/{doc_uid}`
  routes (idempotent delete, 202) with the existing document ownership guard;
  document the explicit deleted semantics of the preview route.

## 2. Library UI

- [ ] Add row actions in library-page: open reader, inline rename (validate
  non-empty, trim, length cap), delete with confirmation that names the
  document and its derived-index impact.
- [ ] Render deleted-document state for evidence chips/cards: "文档已删除",
  disabled locate button, no content; state driven by server facts only.

## 3. Full-document reader

- [ ] Build a paginated reader view on the existing server page-image
  pipeline: page navigation, total pages, fit-width, loading placeholder,
  keyboard paging; entry from library and from evidence preview ("查看全文").
- [ ] Support evidence deep-link: open the reader at the cited page with the
  OCR highlight polygons overlaid (reuse the evidence-preview overlay logic).
- [ ] Reader error states: deleted document, page out of range, preview
  unavailable — server-driven, no mock pages.

## 4. Tests and docs

- [ ] Repository/route tests: rename propagation, idempotent delete, purge
  completeness and reconcile re-drive, retrieval scope exclusion, ownership.
- [ ] UI tests: rename/delete flows, deleted-evidence placeholder, reader
  paging and evidence deep-link, error states.
- [ ] Update README capability table and API docs; run
  `bash scripts/quality_gate.sh core`, `pnpm --dir web test`,
  `pnpm --dir web typecheck`.

## Exit criteria

- [ ] Deleting a document removes it from retrieval, scope and preview
  immediately and irreversibly; historical citations degrade to an explicit
  deleted placeholder with no content leak.
- [ ] Renaming updates the title across list, chips and evidence cards
  without rewriting stored messages.
- [ ] Every supported format is readable end-to-end in the paginated reader,
  and an evidence citation deep-links to the highlighted page.
