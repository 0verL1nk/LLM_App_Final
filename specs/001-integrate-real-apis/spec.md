# Feature Specification: Integrate Real APIs

**Feature Branch**: `001-integrate-real-apis`
**Created**: 2026-01-06
**Status**: Draft
**Input**: User description: "现在结合后端接口,实现前端真实网络请求,禁止所有mock数据展示,如果缺失某些接口,要在后端同步实现"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Authentication (Priority: P1)

Users must be able to log in and register using the real backend authentication system to obtain a valid session token for subsequent requests.

**Why this priority**: Authentication is the gateway to all other features and verifies the basic frontend-backend connectivity.

**Independent Test**: Can be tested by performing login/register actions and verifying the network request returns a valid auth token from the backend database, not a hardcoded string.

**Acceptance Scenarios**:

1. **Given** a registered user, **When** they attempt to log in with valid credentials, **Then** a POST request is sent to the backend, a success response with a token is received, and the user is redirected to the dashboard.
2. **Given** a new user, **When** they register, **Then** a POST request creates the user in the backend database and automatically logs them in.
3. **Given** an invalid login attempt, **When** the backend returns a 401 error, **Then** the frontend displays an appropriate error message without crashing.

---

### User Story 2 - Document Management (Priority: P1)

Users must be able to upload, list, and delete documents, with all operations persisting to the backend storage and database.

**Why this priority**: Core functionality of the application; validates file handling and data persistence.

**Independent Test**: Upload a file, refresh the page, and verify the file is still listed (fetched from backend) and accessible.

**Acceptance Scenarios**:

1. **Given** a logged-in user, **When** they access the document list, **Then** the frontend fetches the list from the backend API, displaying only files belonging to that user.
2. **Given** a selected file, **When** the user uploads it, **Then** the file is sent to the backend, stored, and the list automatically refreshes to show the new file.
3. **Given** a file in the list, **When** the user clicks delete, **Then** a DELETE request removes it from the backend, and it disappears from the UI.

---

### User Story 3 - Text Analysis & Q&A (Priority: P2)

Users must be able to generate summaries, mind maps, and chat with documents using real LLM processing triggered via backend APIs.

**Why this priority**: Delivers the primary value proposition (AI analysis) of the tool.

**Independent Test**: Trigger an analysis task and verify the result text/mindmap data comes from the backend response, not a pre-filled placeholder.

**Acceptance Scenarios**:

1. **Given** a document, **When** the user requests a summary, **Then** the frontend initiates the task, polls/waits for the backend result, and displays the generated summary.
2. **Given** a document, **When** the user asks a question, **Then** the question is sent to the backend, and the LLM's response is displayed in the chat interface.
3. **Given** a document, **When** a mind map is requested, **Then** the structural data is fetched from the backend and rendered visually.

---

### Edge Cases

- What happens when the backend is unreachable? (Frontend should display a connection error, not fallback to mock data).
- What happens when a specific API endpoint is missing or returns 404? (Frontend should handle gracefully, but developers must implement the missing endpoint as per requirements).
- How are session timeouts handled? (401 responses on protected routes should redirect to login).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Frontend MUST be configured to point to the active backend API URL (dynamic configuration based on environment).
- **FR-002**: All data retrieval logic in the frontend MUST use HTTP requests to the backend; all hardcoded JSON objects or "mock" services MUST be removed or disabled.
- **FR-003**: The backend MUST implement any endpoints currently used by the frontend that are not yet available (e.g., specific stats endpoints, user settings, or granular document metadata).
- **FR-004**: Authentication state MUST be managed via tokens received from the backend, stored securely (e.g., localStorage/cookie), and attached to the header of all protected requests.
- **FR-005**: File uploads MUST use `multipart/form-data` to send files to the backend `upload` endpoint.
- **FR-006**: The frontend MUST handle standard HTTP error codes (400, 401, 403, 404, 500) and display user-friendly messages.
- **FR-007**: Asynchronous tasks (like summarization) MUST be handled via the established pattern (e.g., polling status endpoint or WebSocket) if immediate response is not possible.

### Key Entities *(include if feature involves data)*

- **API Client**: The frontend utility/service responsible for making network requests and handling interceptors (auth injection, error logging).
- **User Session**: Represents the state of the currently logged-in user, validated by the backend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of user-visible data in the dashboard and document views is sourced from backend API responses.
- **SC-002**: Zero references to mock data files or hardcoded logic remain in the production execution path.
- **SC-003**: Critical user flows (Login -> Upload -> Analyze) can be completed successfully against a running local or staging backend.
- **SC-004**: Network tab in browser developer tools shows only successful HTTP requests to the backend server during standard usage session.
