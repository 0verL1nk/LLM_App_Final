## ADDED Requirements

### Requirement: Project memory is fully visible and manageable

The system SHALL provide a project-scoped memory management surface listing
every long-term memory item with type, content, updated time and provenance,
filterable by type and searchable by keyword.

#### Scenario: Browsing all memories

- **WHEN** a user opens the memory panel of a project
- **THEN** all long-term memory items are listed with type grouping and
  counts, filterable and searchable
- **AND** provenance is shown only as recorded — "系统整理" when no source
  exists, never fabricated

### Requirement: User CRUD over long-term memory

The system SHALL let the user create, edit and delete memory items through
ownership-checked APIs, with user-managed items marked distinctly, and
changes SHALL take effect in the next run's injected context.

#### Scenario: Correcting a wrong memory

- **WHEN** a user edits a memory item that the system has since updated
- **THEN** the API returns a conflict and the UI shows the newer content
  before allowing a deliberate overwrite

#### Scenario: Deleting a memory

- **WHEN** a user deletes a memory item
- **THEN** it is excluded from context injection immediately and the
  asynchronous consolidator never resurrects it from prior conversations

#### Scenario: Adding a preference

- **WHEN** a user adds a manual memory item (e.g. a terminology convention)
- **THEN** it is stored with a user-managed source marker and participates in
  subsequent retrieval like any other item
