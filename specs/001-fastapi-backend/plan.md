# Implementation Plan: FastAPI Backend Migration

**Branch**: `001-fastapi-backend` | **Date**: 2025-12-23 | **Spec**: `/specs/001-fastapi-backend/spec.md`
**Input**: Feature specification from `/specs/001-fastapi-backend/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Migrate the existing Streamlit-based Literature Reading Assistant to a FastAPI backend with RESTful API, while preserving all existing functionality. The migration will maintain SQLite database, Redis task queue, and integrate with DashScope LLM API. New frontend (React) will communicate via the FastAPI backend.

## Technical Context

**Language/Version**: Python 3.9+ (existing project uses Python 3.9-3.11)
**Primary Dependencies**: FastAPI, SQLAlchemy, RQ (Redis Queue), DashScope API, textract, PyJWT, websockets
**Storage**: SQLite database (existing), file storage in /uploads directory
**Testing**: pytest, pytest-asyncio, pytest-cov (already configured in pyproject.toml)
**Target Platform**: Linux server (Docker support already configured)
**Project Type**: Web backend API (existing codebase in src/llm_app/)
**Performance Goals**: 200ms sync operations, 60s async tasks for <10MB files, 100 concurrent users
**Constraints**: Must maintain compatibility with existing SQLite schema, preserve Redis queue system
**Scale/Scope**: API for literature research assistant supporting 100+ users, file upload/analysis, async task processing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**GATE 1: Incremental Progress** ✓ PASS
- Migrating from Streamlit to FastAPI systematically
- Preserving existing database schema and infrastructure
- Maintaining backward compatibility with existing data
- Clear phased approach: Phase 0 (research) → Phase 1 (design) → Phase 2 (implementation)

**GATE 2: Learning from Existing Code** ✓ PASS
- Will study existing implementation in src/llm_app/
- Analyzing current utils, task queue, and database patterns
- Understanding existing Streamlit pages to maintain feature parity
- Preserving proven patterns from existing codebase

**GATE 3: Architecture Principles** ✓ PASS
- Using FastAPI's dependency injection system
- Separating concerns: API layer, service layer, data access layer
- Explicit dependency management over singletons
- Clear interfaces between components

**GATE 4: Error Handling Strategy** ✓ PASS
- Designing error handling for FastAPI with proper HTTP status codes
- All endpoints will return standardized error responses (code, message, details)
- Logging all security events and failures
- No silent failures - all errors properly reported to client

**GATE 5: Pragmatic Approach** ✓ PASS
- Maintaining SQLite (not upgrading to PostgreSQL unnecessarily)
- Keeping Redis queue (proven solution for async tasks)
- Reusing existing LLM integration code
- Incremental migration rather than complete rewrite

### Post-Design Re-evaluation (After Phase 1)

**GATE 1: Incremental Progress** ✓ STILL PASS
- Design maintains backward compatibility with existing SQLite schema
- Clear phased migration path: foundation → core features → advanced features
- No breaking changes to data model, only additions
- Migration strategy allows parallel development

**GATE 2: Learning from Existing Code** ✓ STILL PASS
- Analyzed existing database schema in utils/utils.py
- Preserved RQ task queue patterns from utils/task_queue.py
- Understanding of DashScope integration from existing API client
- Mapped Streamlit pages to equivalent API endpoints

**GATE 3: Architecture Principles** ✓ STILL PASS
- FastAPI dependency injection for explicit dependencies
- Layered architecture: API → Services → Database
- SQLAlchemy models separate from Pydantic schemas
- Repository pattern can be added if needed (currently direct model access)
- Clear separation of concerns across directories

**GATE 4: Error Handling Strategy** ✓ STILL PASS
- Standardized error responses defined in contracts/*.yaml
- HTTP status codes properly mapped (400, 401, 422, 429, 500)
- Error codes documented (AUTH_INVALID, FILE_TOO_LARGE, etc.)
- Exception handling pattern defined in research.md
- All errors include actionable messages

**GATE 5: Pragmatic Approach** ✓ STILL PASS
- SQLite migration script provided (backward compatible)
- Redis queue retained (rq library, existing workers)
- File storage pattern maintained (/uploads directory)
- OpenAPI contracts generated from existing functionality
- No unnecessary abstractions introduced

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas for API
│   ├── api/             # FastAPI route handlers
│   ├── core/            # Auth, security, config
│   ├── services/        # Business logic
│   ├── queue/           # RQ task processing
│   ├── db/              # Database connection and session
│   └── main.py          # FastAPI application entry point
└── tests/
    ├── contract/        # API contract tests
    ├── integration/     # Full integration tests
    └── unit/            # Unit tests
```

**Structure Decision**: Migrating to a web backend architecture with FastAPI. Using backend/ directory structure to clearly separate API layer. Existing src/llm_app/ contains proven logic that will be refactored into FastAPI pattern.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
