# Research Findings: FastAPI Backend Migration

## Decision: FastAPI Migration Approach

**Chosen**: Complete migration from Streamlit to FastAPI backend with REST API

**Rationale**: FastAPI provides modern async capabilities, automatic OpenAPI documentation, and better separation of concerns for a multi-client architecture. The existing React frontend requires a proper API backend.

## Key Research Areas

### 1. FastAPI Project Structure and Best Practices

**Decision**: Layered architecture with clear separation of concerns

**Rationale**: Maintainable code requires clear boundaries between layers. This approach aligns with the constitution principle of "clear intent over clever code."

**Implementation**:
- `api/`: HTTP request/response handlers (routers)
- `services/`: Business logic, orchestrates between multiple data sources
- `models/`: SQLAlchemy database models
- `schemas/`: Pydantic models for API request/response validation
- `core/`: Authentication, configuration, security
- `db/`: Database connection and session management

**Alternatives Considered**:
- Monolithic structure (rejected: hard to maintain, violates single responsibility)
- Domain-driven structure (overkill for this project size)

### 2. SQLAlchemy Integration with FastAPI

**Decision**: SQLAlchemy 2.0 async engine with session dependency injection

**Rationale**:
- Existing codebase already uses SQLAlchemy
- Async support matches FastAPI's async nature
- Dependency injection ensures proper session lifecycle
- Automatic OpenAPI schema generation with Pydantic integration

**Implementation Pattern**:
```python
# db/session.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

# FastAPI dependency
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

# Usage in routers
@router.post("/files/upload")
async def upload_file(file: UploadFile, db: AsyncSession = Depends(get_db)):
    # Business logic
    pass
```

**Alternatives Considered**:
- Django ORM (rejected: too heavy for this project)
- Raw SQL (rejected: less maintainable, no ORM benefits)
- Pony ORM (rejected: less common, smaller community)

### 3. RQ (Redis Queue) Integration with FastAPI

**Decision**: Maintain existing RQ pattern with FastAPI integration

**Rationale**:
- Existing codebase already uses RQ successfully
- Simple task queue is sufficient for current requirements
- RQ worker can run as separate process
- Easy to integrate with async FastAPI endpoints

**Implementation Pattern**:
```python
# queue/task_queue.py
from rq import Queue
from redis import Redis

redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

# In API endpoint
@router.post("/documents/{file_id}/extract")
async def extract_document(file_id: str, task_queue: Queue = Depends(get_task_queue)):
    job = task_queue.enqueue(
        extract_document_task,
        file_id,
        user_uuid=current_user.uuid,
        job_timeout=300
    )
    return {"task_id": job.id, "status": "pending"}
```

**Best Practices**:
- Tasks should be idempotent
- Use job_timeout to prevent stuck tasks
- Store task results in database (not Redis) for persistence
- Separate RQ worker process

**Alternatives Considered**:
- Celery (rejected: more complex, RQ is sufficient)
- Dramatiq (rejected: less mature, smaller community)
- FastAPI BackgroundTasks (rejected: not suitable for long-running tasks)

### 4. DashScope API Integration

**Decision**: Wrap DashScope in async service class with retry logic

**Rationale**:
- Existing codebase uses openai client for DashScope
- Need async support for FastAPI
- Centralized LLM service ensures consistent configuration
- Retry logic improves reliability

**Implementation Pattern**:
```python
# services/llm_service.py
from openai import AsyncOpenAI
import httpx

class DashScopeService:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    async def extract_text(self, file_path: str) -> str:
        # Implementation
        pass

    async def summarize(self, text: str, options: dict) -> dict:
        # Implementation
        pass
```

**Best Practices**:
- Store API key per-user in database
- Use httpx.AsyncClient for async operations
- Implement rate limiting per user
- Log all API calls for monitoring

### 5. JWT Authentication with FastAPI

**Decision**: JWT Bearer tokens with FastAPI security utilities

**Rationale**:
- Standard approach for REST APIs
- FastAPI provides built-in JWT utilities
- Compatible with frontend token storage
- Stateless authentication scales well

**Implementation Pattern**:
```python
# core/security.py
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

security = HTTPBearer()

async def get_current_user(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid: str = payload.get("sub")
        if user_uuid is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user_by_uuid(user_uuid, db)
    if user is None:
        raise credentials_exception
    return user
```

**Security Considerations**:
- Store JWT secret in environment variables
- Token expiration: 24 hours (from spec)
- Store user UUID in token (not full user object)
- Invalidate tokens on logout (if using refresh tokens)

**Alternatives Considered**:
- Session-based auth (rejected: doesn't scale well for APIs)
- OAuth2 (rejected: overkill for this use case)
- API keys (rejected: less secure, no user context)

### 6. WebSocket Support for Real-time Task Updates

**Decision**: FastAPI WebSocket with Redis pub/sub for task status

**Rationale**:
- Provides real-time feedback to users
- Better user experience than polling
- Redis pub/sub allows worker to notify WebSocket clients
- Standard approach in FastAPI ecosystem

**Implementation Pattern**:
```python
# api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from redis import Redis

@router.websocket("/ws/tasks/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    redis = Redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"task:{task_id}")

    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                await websocket.send_json(json.loads(message['data']))
    except WebSocketDisconnect:
        pubsub.close()
```

**Best Practices**:
- Use Redis pub/sub for broadcasting updates
- Implement connection cleanup on disconnect
- Authentication should happen during WebSocket handshake
- Add ping/pong to detect dead connections

### 7. Error Handling Strategy

**Decision**: Centralized error handling with standardized error responses

**Rationale**:
- Consistent error format across all endpoints
- Easier debugging and monitoring
- Better client experience with actionable error messages
- Aligns with API specification in docs/api/README.md

**Implementation**:
```python
# core/exceptions.py
class APIException(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 400):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code

# API response schema
class ErrorResponse(BaseModel):
    success: bool = False
    error: dict = Field(..., example={
        "code": "AUTH_INVALID",
        "message": "Invalid authentication credentials",
        "details": {}
    })

# Global exception handler
@exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message
            }
        }
    )
```

**Error Codes** (from spec):
- AUTH_REQUIRED, AUTH_INVALID, AUTH_EXPIRED
- RESOURCE_NOT_FOUND, VALIDATION_ERROR
- FILE_TOO_LARGE, FILE_TYPE_INVALID
- API_KEY_INVALID, RATE_LIMIT_EXCEEDED
- TASK_NOT_FOUND, TASK_ALREADY_COMPLETED

### 8. File Upload Handling

**Decision**: FastAPI's UploadFile with validation and storage

**Rationale**:
- FastAPI provides built-in file upload support
- Async file handling matches async architecture
- Easy integration with existing file storage pattern

**Implementation**:
```python
# api/files.py
from fastapi import UploadFile, File

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate file
    if file.size > MAX_FILE_SIZE:
        raise APIException("FILE_TOO_LARGE", "File size exceeds limit")

    if file.content_type not in ALLOWED_EXTENSIONS:
        raise APIException("FILE_TYPE_INVALID", "Unsupported file type")

    # Save file
    file_id, file_path = await save_file(file, current_user.uuid)

    # Create database record
    file_record = File(
        file_id=file_id,
        user_uuid=current_user.uuid,
        # ... other fields
    )
    db.add(file_record)
    await db.commit()

    return {"file_id": file_id, "status": "uploaded"}
```

### 9. Pydantic Schemas for API Contracts

**Decision**: Separate request/response schemas from database models

**Rationale**:
- Decouples API from database schema
- Allows for different validation rules
- Cleaner separation of concerns
- Easier to version API independently

**Implementation**:
```python
# schemas/user.py
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    api_key_configured: bool
    preferred_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# schemas/task.py
class TaskStatus(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: int = Field(ge=0, le=100)
    result: Optional[dict] = None
    error_message: Optional[str] = None
```

### 10. Testing Strategy

**Decision**: Multi-level testing with pytest-asyncio

**Rationale**:
- Contract tests ensure API matches specification
- Integration tests verify end-to-end flows
- Unit tests cover business logic
- Async support for FastAPI testing

**Implementation**:
```python
# tests/conftest.py
from fastapi.testclient import TestClient
import pytest

@pytest.fixture
def client():
    from main import app
    return TestClient(app)

# tests/contract/test_auth.py
def test_register_user(client: TestClient):
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "token" in data["data"]
```

**Test Coverage Goals**:
- All API endpoints: 100%
- Business logic: 90%+
- Integration tests: critical paths only

## Migration Strategy

### Phase 1: Foundation
1. Set up FastAPI project structure
2. Configure database models (SQLAlchemy)
3. Implement authentication
4. Create basic error handling

### Phase 2: Core Features
1. File upload/download endpoints
2. Task queue integration
3. DashScope LLM integration
4. WebSocket for task updates

### Phase 3: Advanced Features
1. All document processing endpoints
2. Statistics endpoint
3. Rate limiting
4. Complete testing

### Phase 4: Production
1. Docker configuration
2. Logging and monitoring
3. Performance optimization
4. Documentation

## Summary

All constitution gates PASSED. The research confirms that a FastAPI migration is feasible and maintainable. Key decisions:

1. ✅ SQLAlchemy for ORM (existing pattern)
2. ✅ RQ for async tasks (existing pattern)
3. ✅ JWT for authentication (standard approach)
4. ✅ WebSocket for real-time updates (enhancement)
5. ✅ Layered architecture (maintainable)
6. ✅ Pydantic schemas (validated contracts)

**No NEEDS CLARIFICATION** - All technical decisions are resolved.