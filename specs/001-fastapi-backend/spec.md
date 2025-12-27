# Feature Specification: FastAPI Backend Migration

**Feature Branch**: `001-fastapi-backend`
**Created**: 2025-12-23
**Status**: Draft
**Input**: User description: "看下目前的项目,我刚做了新前端,不用streamlit了,现在需要根据接口文档docs/api/README.md将项目改为后端,使用fastapi,注意项目规范,注意最佳实践"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - API Authentication System (Priority: P1)

As a user of the frontend application, I need to authenticate with the backend API so that I can securely access all protected features.

**Why this priority**: Authentication is the foundation of all other features. Without it, no user data or operations can be secured.

**Independent Test**: Can be fully tested by registering a new account, logging in with credentials, and verifying that authenticated requests succeed while unauthenticated requests fail with appropriate 401 errors.

**Acceptance Scenarios**:

1. **Given** a valid username, email, and password, **When** I register a new account, **Then** I receive a JWT token valid for 24 hours and can access protected endpoints
2. **Given** valid username and password, **When** I log in, **Then** I receive a JWT token and user profile information
3. **Given** an expired JWT token, **When** I make an authenticated request, **Then** I receive a 401 error with AUTH_EXPIRED code
4. **Given** an invalid token, **When** I make an authenticated request, **Then** I receive a 401 error with AUTH_INVALID code
5. **Given** a valid token, **When** I log out, **Then** the token is invalidated server-side

---

### User Story 2 - File Upload and Management (Priority: P1)

As a researcher, I need to upload research papers (PDF, DOCX, TXT) to the system so that I can process and analyze them.

**Why this priority**: File upload is the entry point for all document processing features. Without it, users cannot begin working with their documents.

**Independent Test**: Can be fully tested by uploading a file via multipart/form-data, receiving a file_id, and verifying the file appears in the list with correct metadata.

**Acceptance Scenarios**:

1. **Given** a valid PDF/DOCX/TXT file under size limit, **When** I upload it via multipart form, **Then** I receive a unique file_id and can download/view the file
2. **Given** a file that's already uploaded (same MD5), **When** I upload it again, **Then** the system deduplicates and returns the existing file_id
3. **Given** a file over the size limit, **When** I upload it, **Then** I receive a 422 error with FILE_TOO_LARGE code
4. **Given** an unsupported file type, **When** I upload it, **Then** I receive a 422 error with FILE_TYPE_INVALID code
5. **Given** uploaded files, **When** I query the file list with pagination, **Then** I receive a paginated list with correct metadata (name, size, status, tags)
6. **Given** a file_id, **When** I delete the file, **Then** the file is permanently removed from storage

---

### User Story 3 - Document Text Extraction (Priority: P1)

As a researcher, I need to extract text from uploaded documents so that I can analyze the content.

**Why this priority**: Text extraction is required for all downstream AI processing tasks (summarization, Q&A, rewriting, mindmaps). It's the first step in document analysis.

**Independent Test**: Can be fully tested by uploading a document, calling the extract endpoint, polling task status, and receiving extracted text with metadata (page count, word count, sections).

**Acceptance Scenarios**:

1. **Given** an uploaded file, **When** I request text extraction, **Then** I receive a task_id and can poll for status
2. **Given** a text extraction task is running, **When** I poll the task status, **Then** I see progress updates from 0-100%
3. **Given** extraction completes successfully, **When** I check task status, **Then** I receive extracted text, sections, and metadata (page count, word count, language)
4. **Given** extraction fails (corrupted file), **When** I check task status, **Then** I see failed status with error_message
5. **Given** an existing extraction task, **When** I submit the same file_id again, **Then** I can retrieve the previous result

---

### User Story 4 - Document Summarization (Priority: P2)

As a researcher, I need to generate summaries of my documents so that I can quickly understand key points and main arguments.

**Why this priority**: Summarization is a primary value proposition of the application. It helps researchers save time and grasp document content efficiently.

**Independent Test**: Can be fully tested by requesting a summary for an extracted document and receiving a structured summary with key points and statistics.

**Acceptance Scenarios**:

1. **Given** a successfully extracted document, **When** I request a summary with brief type, **Then** I receive a concise summary with key points
2. **Given** a successfully extracted document, **When** I request a detailed summary, **Then** I receive a comprehensive summary with section-by-section breakdowns
3. **Given** a successfully extracted document, **When** I request a custom summary with focus areas, **Then** I receive a summary highlighting those specific areas
4. **Given** a summary task, **When** I check the result, **Then** I see statistics (original length, summary length, compression ratio)

---

### User Story 5 - Document Question Answering (Priority: P2)

As a researcher, I need to ask questions about my documents and get accurate answers with sources so that I can deep-dive into specific topics.

**Why this priority**: Interactive Q&A provides direct value to researchers by allowing them to query documents naturally and receive contextual answers.

**Independent Test**: Can be fully tested by asking a question about an extracted document and receiving an answer with confidence score and source citations.

**Acceptance Scenarios**:

1. **Given** an extracted document, **When** I ask a question about its content, **Then** I receive an answer with a confidence score (0-1) and source citations
2. **Given** a question that cannot be answered from the document, **When** I ask it, **Then** I receive a low confidence answer indicating insufficient information
3. **Given** a question with chat history, **When** I ask a follow-up question, **Then** the system uses context from previous exchanges
4. **Given** successful Q&A, **When** I receive a response, **Then** I also receive suggested follow-up questions

---

### User Story 6 - Text Rewriting (Priority: P3)

As a researcher, I need to rewrite text sections in different styles so that I can adapt content for different audiences or purposes.

**Why this priority**: Text rewriting is a valuable feature for researchers who need to repurpose content for different contexts (e.g., making formal text more casual, or vice versa).

**Independent Test**: Can be fully tested by providing text and rewrite parameters, then receiving rewritten text with improvements and alternatives.

**Acceptance Scenarios**:

1. **Given** academic text, **When** I request casual rewriting, **Then** I receive the text rewritten in a more accessible style
2. **Given** formal text, **When** I request creative rewriting, **Then** I receive a more engaging version with creative language
3. **Given** long text, **When** I request concise rewriting, **Then** I receive a shorter version maintaining key points
4. **Given** text rewriting, **When** I receive results, **Then** I see improvements made and alternative versions

---

### User Story 7 - Mind Map Generation (Priority: P3)

As a researcher, I need to generate visual mind maps of my documents so that I can better understand document structure and relationships between concepts.

**Why this priority**: Visual representation helps researchers grasp document structure and see connections between ideas at a glance.

**Independent Test**: Can be fully tested by requesting a mindmap for an extracted document and receiving a hierarchical tree structure with branches and keywords.

**Acceptance Scenarios**:

1. **Given** an extracted document, **When** I request a mindmap, **Then** I receive a hierarchical tree structure with center topic and branches
2. **Given** a mindmap request with max_depth=3, **When** the mindmap is generated, **Then** it contains at most 3 levels of depth
3. **Given** a mindmap request with include_keywords=true, **When** it completes, **Then** I receive a list of extracted keywords
4. **Given** a mindmap task, **When** I check the structure result, **Then** I see total_branches, max_depth, and main_topics

---

### User Story 8 - Task Management and Monitoring (Priority: P2)

As a user, I need to monitor long-running tasks so that I can track progress and understand when results are ready.

**Why this priority**: All AI processing tasks (extraction, summarization, mindmaps) are asynchronous. Users need visibility into task status to understand when to retrieve results.

**Independent Test**: Can be fully tested by creating an extraction task, polling task status, and seeing status transitions from pending → processing → completed/failed.

**Acceptance Scenarios**:

1. **Given** an async task is created, **When** I query the task status, **Then** I see current status (pending/processing/completed/failed) and progress percentage
2. **Given** a completed task, **When** I query the task, **Then** I see completion time and result data
3. **Given** a failed task, **When** I query the task, **Then** I see error_message explaining the failure
4. **Given** a running task, **When** I request cancellation, **Then** the task is marked as cancelled
5. **Given** multiple tasks, **When** I query my task list, **Then** I see all tasks with pagination and can filter by status/type

---

### User Story 9 - User Profile and Configuration (Priority: P2)

As a user, I need to manage my API keys and preferences so that I can configure the system to use my own DashScope account and preferred models.

**Why this priority**: Users need to configure their own API keys to use the service, and preferences ensure consistent behavior across all their requests.

**Independent Test**: Can be fully tested by updating API key in user profile and verifying it's used for subsequent API calls.

**Acceptance Scenarios**:

1. **Given** I'm logged in, **When** I view my profile, **Then** I see my username, email, whether API key is configured, and my preferred model
2. **Given** I'm logged in without an API key, **When** I update my API key, **Then** it's securely stored and I can use it for document processing
3. **Given** I'm logged in, **When** I update my preferred model, **Then** all future requests use the new model setting
4. **Given** an invalid API key, **When** I try to process a document, **Then** I receive an error with API_KEY_INVALID code

---

### User Story 10 - Statistics and Monitoring (Priority: P3)

As a user, I need to view usage statistics so that I can understand my resource consumption and track my productivity.

**Why this priority**: Transparency about API usage (calls, tokens) helps users manage costs and understand their activity patterns.

**Independent Test**: Can be fully tested by viewing the statistics endpoint and seeing file counts, API call counts, and task completion metrics.

**Acceptance Scenarios**:

1. **Given** I'm logged in, **When** I view statistics, **Then** I see counts of total/processed/processing files and monthly file count
2. **Given** I've been using the system, **When** I view statistics, **Then** I see total API calls, total tokens consumed, and this month's call count
3. **Given** I've completed tasks, **When** I view statistics, **Then** I see total completed tasks, pending tasks, and average completion time

---

### Edge Cases

- What happens when the same user uploads the same file twice? (Deduplication by MD5)
- What happens when Redis is down during task processing? (Error handling, task status persistence in SQLite)
- What happens when the API key is invalid or expired? (Clear error messages, guide user to update)
- What happens when the system is under high load? (Rate limiting, queue backpressure)
- What happens when a file fails text extraction? (Mark task as failed, allow retry)
- What happens when users exceed their quota? (Rate limiting with 429 errors)
- What happens when document processing times out? (Task timeout handling, clear error messages)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement RESTful API with JSON responses matching the documented schema in docs/api/README.md
- **FR-002**: System MUST use JWT Bearer token authentication for all protected endpoints
- **FR-003**: System MUST support user registration with username, email, and password validation
- **FR-004**: System MUST support user login with username/password and return JWT token with expiration
- **FR-005**: System MUST support file upload via multipart/form-data with validation for type and size
- **FR-006**: System MUST implement file deduplication using MD5 hashing
- **FR-007**: System MUST support pagination for file lists and task lists with configurable page_size (max 100)
- **FR-008**: System MUST implement async task processing for text extraction, summarization, and mindmap generation
- **FR-009**: System MUST integrate with DashScope API for all LLM operations (extraction, summarization, Q&A, rewriting)
- **FR-010**: System MUST support WebSocket connections for real-time task progress updates
- **FR-011**: System MUST implement rate limiting to prevent API abuse
- **FR-012**: System MUST support multiple summarization types: brief, detailed, and custom with focus areas
- **FR-013**: System MUST support multiple rewrite types: academic, casual, formal, creative, concise
- **FR-014**: System MUST generate mindmaps as hierarchical tree structures with configurable depth (1-5)
- **FR-015**: System MUST provide confidence scores (0-1) for Q&A responses with source citations
- **FR-016**: System MUST return standard error responses with error codes matching the documented specification
- **FR-017**: System MUST persist all data in SQLite database with the existing schema
- **FR-018**: System MUST use Redis for async task queuing (RQ) and WebSocket connection management
- **FR-019**: System MUST support file download via authenticated download URLs
- **FR-020**: System MUST log all authentication events and security-related operations
- **FR-021**: System MUST allow users to configure their own DashScope API keys per-user
- **FR-022**: System MUST support context-aware Q&A with chat history
- **FR-023**: System MUST generate suggested questions based on document content
- **FR-024**: System MUST provide statistics endpoint showing file counts, API usage, and task metrics

### Key Entities

- **User**: Represents authenticated users with username, email, password hash, optional API key, and preferred model
- **File**: Represents uploaded documents with original filename, UUID filename, MD5 hash, MIME type, size, processing status, and optional tags
- **Content**: Represents generated content (extracted text, summaries, mindmaps) linked to files
- **Task**: Represents async operations (extract, summarize, rewrite, mindmap) with status, progress, and results
- **Token**: Represents authentication tokens with user_id, expiration, and revocation status
- **Statistics**: Represents aggregated usage metrics for files, API calls, tokens, and tasks

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All API endpoints respond within 200ms for synchronous operations (authentication, file metadata)
- **SC-002**: Async tasks complete within 60 seconds for documents under 10MB
- **SC-003**: System handles 100 concurrent users without degradation
- **SC-004**: All endpoints return correct HTTP status codes and response schemas matching docs/api/README.md
- **SC-005**: JWT tokens expire correctly after 24 hours and are validated on every protected request
- **SC-006**: File uploads support files up to 50MB with proper error messages for oversized files
- **SC-007**: Task processing is reliable with 99% success rate for valid documents
- **SC-008**: Database queries for file lists execute in under 100ms with pagination
- **SC-009**: API supports all documented file types (PDF, DOCX, TXT) with proper validation
- **SC-010**: Rate limiting prevents abuse while allowing normal usage patterns
- **SC-011**: WebSocket connections provide real-time task progress updates with less than 5 second latency
- **SC-012**: Summarization API returns results with compression ratio between 10-50% of original length
- **SC-013**: Q&A responses include confidence scores and at least one source citation
- **SC-014**: Mindmap generation produces hierarchical structures with 2-5 main branches
- **SC-015**: User API keys are securely stored and used exclusively for that user's requests
- **SC-016**: Error responses include meaningful messages and correct error codes from the specification
- **SC-017**: Statistics endpoint updates within 5 seconds of task completion
- **SC-018**: System logs all security events (login, logout, failed auth, API key updates)

## Assumptions

- Frontend application will handle JWT token storage and include it in Authorization headers
- DashScope API is accessible and users have valid API keys
- Redis server is available and running for task queuing
- File storage directory (/uploads) has sufficient disk space
- Existing SQLite database schema is compatible or will be migrated
- Users can configure their own DashScope API keys through the API
- Long-running tasks (extraction, summarization) are acceptable as async operations
- WebSocket support is implemented but polling remains a valid fallback

## Dependencies

- **FastAPI**: Web framework for building the API
- **SQLAlchemy**: ORM for database operations
- **Alembic**: Database migration management
- **RQ (Redis Queue)**: Async task processing
- **Redis**: Task queue and WebSocket support
- **DashScope API**: LLM integration for all AI features
- **textract**: Document text extraction library
- **PyJWT**: JWT token management
- **python-multipart**: File upload handling
- **websockets**: WebSocket support for real-time updates

## Out of Scope

- User interface design and implementation (handled by frontend team)
- Mobile application support
- Multi-language UI localization
- User management admin panel
- Bulk file operations (upload multiple files in single request)
- Document format conversion (PDF to DOCX, etc.)
- Full-text search across all user files
- Document sharing and collaboration features
- Advanced analytics beyond basic usage statistics
- Integration with external reference managers (Zotero, Mendeley)