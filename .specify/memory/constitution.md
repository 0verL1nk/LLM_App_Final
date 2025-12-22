<!--
Sync Impact Report:
Version change: NEW (initial creation)
Added sections: I-VII Core Principles (Modular Architecture, Type Safety, Test-First Development, Code Quality, Documentation, Async Task Processing, Data Security), Technical Standards (Stack/Development/File Org), Development Workflow (Contribution/Quality/Task Organization), Governance (Amendment/Version/Compliance)
Removed sections: None (initial creation)
Templates updated: ✅ .specify/templates/plan-template.md (Constitution Check section updated with specific compliance requirements)
Follow-up TODOs: None
--丐

# Literature Reading Assistant Constitution

## Core Principles

### I. Modular Architecture
Every feature MUST reside in a dedicated module within `src/llm_app/` with clear boundaries. Modules must be self-contained, independently testable, and follow the single responsibility principle. Shared utilities MUST be placed in appropriate `src/llm_app/*/` subdirectories (core/, api/, queue/, ui/). This ensures code reuse, maintainability, and enables parallel development across different components.

### II. Type Safety (NON-NEGOTIABLE)
All Python code MUST include complete type annotations (100% coverage). Every function, class, and method MUST have type hints following PEP 484 standards. MyPy type checking MUST pass without errors before code is committed. This prevents runtime errors, improves IDE support, and serves as documentation for expected data structures and return types.

### III. Test-First Development (NON-NEGOTIABLE)
Test-Driven Development is mandatory for all new features. Developers MUST write failing tests first, then implement the minimum code to pass those tests. Unit tests MUST achieve minimum 70% code coverage across all modules. Test files MUST be organized in `tests/unit/`, `tests/integration/`, and `tests/contract/` directories. All tests MUST pass before merging any feature branch.

### IV. Code Quality Enforcement
Every code change MUST pass automated quality checks without warnings. Ruff linting MUST pass with zero violations (auto-fixable violations must be resolved). Bandit security scanning MUST report no high-severity issues. MyPy type checking MUST pass with strict settings. These checks are enforced via pre-commit hooks and CI/CD pipeline to maintain consistent, secure, and readable code.

### V. Documentation Standards
All modules, classes, and public functions MUST include docstrings following NumPy/Sphinx style. README.md MUST be kept current with each feature addition. Architecture documentation MUST be updated in `docs/architecture.md` for any structural changes. API changes MUST be reflected in `docs/api_reference.md`. Every user-facing feature MUST have clear documentation and examples.

### VI. Asynchronous Task Processing
Long-running operations (LLM API calls, document processing, analysis) MUST be handled through the asynchronous task queue system (Redis + RQ). Task status MUST be tracked in SQLite database for user feedback. Background workers MUST be monitored and logged appropriately. This ensures responsive UI and prevents timeout issues during heavy processing.

### VII. Data Persistence & Security
User data, uploaded files, and generated content MUST be securely stored with appropriate access controls. API keys MUST be encrypted or hashed before storage (TODO noted in utils.py:157). File uploads MUST be validated and sanitized. SQLite database operations MUST use parameterized queries to prevent SQL injection. All sensitive operations MUST be logged for audit trails.

## Technical Standards

### Stack Requirements
- **Language**: Python 3.9+ (recommended 3.11+)
- **Frontend**: Streamlit 1.40+ for UI layer
- **Backend**: Python with async/await patterns for I/O-bound operations
- **Database**: SQLite for development, PostgreSQL migration planned
- **Task Queue**: Redis + RQ for async operations (memory mode available for dev)
- **LLM Integration**: LangChain 0.3.x with DashScope/OpenAI-compatible APIs
- **Visualization**: pyecharts 2.0+ for interactive charts and mind maps
- **Package Management**: uv package manager (REQUIRED for consistency)

### Development Standards
- **Code Style**: PEP 8 enforced via Ruff
- **Type Checking**: MyPy with strict mode enabled
- **Security**: Bandit security linter
- **Testing**: pytest framework with coverage reporting
- **Pre-commit**: All hooks MUST pass before commit
- **CI/CD**: GitHub Actions pipeline for multi-platform testing

### File Organization
- **Source Code**: `src/llm_app/` (module-based structure)
- **Tests**: `tests/` organized by type (unit/integration/contract)
- **Documentation**: `docs/` with architecture, API reference, migration guides
- **Pages**: Streamlit pages in `pages/` directory
- **Configuration**: `pyproject.toml` for all tool configurations

## Development Workflow

### Contribution Process
1. Create feature branch following naming convention `###-feature-name`
2. Write failing tests first (Test-First principle)
3. Implement minimum code to pass tests
4. Run `make dev-check` to ensure all quality gates pass
5. Update relevant documentation
6. Submit PR with detailed description and test results
7. Code review MUST verify compliance with all constitutional principles
8. CI/CD checks MUST pass on all platforms (Ubuntu/Windows/macOS, Python 3.9/3.10/3.11)

### Quality Gates
**MANDATORY**: Every PR MUST pass:
- Ruff linting (zero violations)
- MyPy type checking (zero errors)
- Bandit security scan (zero high-severity issues)
- pytest unit tests (70%+ coverage minimum)
- Multi-platform CI/CD validation
- Documentation review (if structural changes)

### Task Organization
Tasks MUST be organized by user story for independent implementation and testing. Each story MUST deliver standalone value without depending on other stories. Foundational infrastructure (database, auth, queue) MUST be completed before any user story work begins. Tasks MUST be traced back to specific user scenarios and acceptance criteria.

## Governance

### Amendment Process
Constitutional changes require:
1. RFC (Request for Comments) with detailed rationale
2. Community discussion and approval
3. Migration plan for breaking changes
4. Updated version following semantic versioning (MAJOR.MINOR.PATCH)
5. Documentation updates across all affected areas
6. Backward compatibility assessment

### Version Policy
- **MAJOR**: Breaking changes to architecture, API, or core principles
- **MINOR**: New features, principles, or significant framework additions
- **PATCH**: Clarifications, typo fixes, non-breaking improvements

**Current Version**: 1.0.0 | **Ratified**: 2025-12-22 | **Last Amended**: 2025-12-22

### Compliance Verification
All PR reviews MUST explicitly verify:
- Modular architecture boundaries are respected
- Type annotations are complete and accurate
- Tests demonstrate failing-before-implementing workflow
- Code quality tools pass without warnings
- Documentation is current and comprehensive
- Async task patterns are followed appropriately
- Security best practices are maintained

**Note**: This constitution supersedes all other development practices. Any deviation MUST be justified in writing and approved through the amendment process.