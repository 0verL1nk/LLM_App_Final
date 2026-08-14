## ADDED Requirements

### Requirement: PaperDraft is the authoring authority

The system SHALL persist a project-owned `PaperDraft` with a canonical LaTeX source
tree and immutable revisions. Chat messages SHALL NOT be treated as source authority.

#### Scenario: Concurrent editor save

- **WHEN** a client saves against a stale base revision
- **THEN** the server rejects the write with a revision conflict
- **AND THEN** it preserves both the current source and the proposed change for review

### Requirement: Compile artifacts are real and failure-safe

The system SHALL expose only server-produced PDF artifacts and normalized compiler
diagnostics. A failed compilation SHALL preserve the previous successful artifact.

#### Scenario: Compile error

- **WHEN** a LaTeX compile attempt fails
- **THEN** the owner receives bounded file/line diagnostics from the server
- **AND THEN** the workspace continues to display the latest successful PDF, if one exists
- **AND THEN** no placeholder PDF or fabricated progress is rendered

### Requirement: AI changes require reviewable revisions

The system SHALL store an AI-proposed manuscript change as a revision based on an
explicit draft and source span before it may update canonical source.

#### Scenario: Evidence-backed edit proposal

- **WHEN** AI proposes a factual edit to a selected LaTeX span
- **THEN** the revision records its base revision and claim-to-evidence provenance
- **AND THEN** the user can accept or reject it without destructive overwrite

### Requirement: Workspace makes writing primary and AI collaborative

The desktop workspace SHALL show editable source and the latest compiled PDF as primary
views, while AI conversation is a docked or floating collaboration surface.

#### Scenario: Active research while editing

- **WHEN** an AI research Run is active and the user sends a follow-up from the docked panel
- **THEN** the input follows the durable SteeringInput boundary rules
- **AND THEN** the source editor and latest PDF remain visible and usable

### Requirement: Cloud selection requires authenticated compatibility

The desktop SHALL enable a remote mode only after it has a real authenticated endpoint
and has verified the required API capability version.

#### Scenario: Remote endpoint is not configured

- **WHEN** no authenticated compatible remote endpoint is available
- **THEN** the account area identifies local mode as active
- **AND THEN** it does not offer a deceptive cloud switch
