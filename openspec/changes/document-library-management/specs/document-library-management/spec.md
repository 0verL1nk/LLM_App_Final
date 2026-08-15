## ADDED Requirements

### Requirement: Document deletion is immediate and complete

The system SHALL remove a deleted document from retrieval scope, listing and
preview immediately, and SHALL purge all derived artifacts (vector chunks,
page images, OCR artifacts, original file) as retryable, reconcile-driven
steps. Deletion SHALL be idempotent.

#### Scenario: Delete removes the document everywhere

- **WHEN** a user deletes a published document
- **THEN** subsequent retrieval returns no hits from it and the document
  disappears from the library and the searchable scope
- **AND** the preview route returns an explicit deleted-document error rather
  than content

#### Scenario: Historical citation after deletion

- **WHEN** a past message cites a deleted document
- **THEN** the citation renders an explicit "文档已删除" placeholder with the
  locate action disabled
- **AND** no page content or highlight data of the deleted document is served

### Requirement: Document rename updates current metadata only

The system SHALL let the user rename a document, and all current surfaces
(library list, evidence chips, evidence cards) SHALL display the new title
without rewriting stored message history.

#### Scenario: Rename propagates to current display

- **WHEN** a user renames a document
- **THEN** the library list, new evidence chips and evidence cards show the
  new title
- **AND** previously stored message text is not rewritten

### Requirement: Paginated full-document reader

The system SHALL provide a paginated reader for every supported format built
on the server page-image pipeline, with page navigation and evidence
deep-linking to the cited page with OCR highlights.

#### Scenario: Open a document for full reading

- **WHEN** a user opens a published document from the library
- **THEN** the reader shows its pages with navigation and total page count
  for any supported format (PDF, Office-converted, image, TXT)

#### Scenario: Deep-link from evidence

- **WHEN** a user opens the reader from an evidence citation
- **THEN** the reader opens at the cited page and overlays the OCR highlight
  polygons from server-provided evidence facts
