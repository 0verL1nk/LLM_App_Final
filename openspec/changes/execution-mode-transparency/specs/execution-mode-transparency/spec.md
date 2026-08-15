## ADDED Requirements

### Requirement: Execution route transparency

Every run SHALL expose its persisted execution route (requested mode,
resolved mode, reason) through server facts, and the UI SHALL render it for
both live and reloaded views.

#### Scenario: Auto request resolves to a different mode

- **WHEN** a user submits with mode "auto" and the server resolves it to
  `plan_execute`
- **THEN** the assistant message shows an "Auto → Plan-Execute" style badge
- **AND** the inspector shows the full routing record with a human-readable
  reason

#### Scenario: Invalid selection falls back

- **WHEN** an invalid mode override causes a documented fallback
- **THEN** the badge renders with a warning style naming the fallback reason

#### Scenario: Legacy run without a route record

- **WHEN** a historical run has no persisted execution route
- **THEN** no badge is fabricated and the inspector shows an explicit
  no-record state
