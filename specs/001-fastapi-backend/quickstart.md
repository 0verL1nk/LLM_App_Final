# Quick Start Guide: FastAPI Backend

This guide will help you set up and run the FastAPI backend for the Literature Reading Assistant.

## Prerequisites

- Python 3.9 or higher
- Redis server (for task queue)
- SQLite (included with Python)
- uv package manager (recommended)

## Installation

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync --no-install-project

# Or using pip
pip install -r requirements.txt
```

### 2. Install Additional FastAPI Dependencies

Add to your `pyproject.toml`:

```toml
dependencies = [
    # Existing dependencies...
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "pydantic>=2.5.0",
    "python-multipart>=0.0.6",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "aiofiles>=23.0.0",
    "websockets>=12.0",
]
```

### 3. Set Up Environment Variables

Create `.env` file in project root:

```bash
# Required
DASHSCOPE_API_KEY=your_dashscope_api_key

# Database
DATABASE_URL=sqlite+aiosqlite:///./database.sqlite

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME="Literature Reading Assistant"
DEBUG=True
```

### 4. Initialize Database

```bash
# Create database tables
python -c "from backend.src.db.database import init_db; import asyncio; asyncio.run(init_db())"
```

### 5. Start Redis Server

```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or install locally
redis-server
```

## Running the Application

### Development Mode

```bash
# Start FastAPI server with hot reload
uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8501

# Or using Python
python -m uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8501
```

The API will be available at:
- **API Documentation**: http://localhost:8501/docs
- **ReDoc**: http://localhost:8501/redoc
- **Base URL**: http://localhost:8501/api/v1

### Production Mode

```bash
# Using uvicorn with multiple workers
uvicorn backend.src.main:app --host 0.0.0.0 --port 8501 --workers 4

# Or using gunicorn
gunicorn backend.src.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Starting the RQ Worker

```bash
# Start RQ worker for task processing
rq worker tasks --url redis://localhost:6379/0

# With custom queue name
rq worker tasks --url redis://localhost:6379/0 --with-scheduler
```

## API Usage Examples

### 1. Register a User

```bash
curl -X POST http://localhost:8501/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher123",
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "researcher123",
    "email": "user@example.com",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2024-12-24T10:00:00Z"
  }
}
```

### 2. Login

```bash
curl -X POST http://localhost:8501/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher123",
    "password": "securepassword123"
  }'
```

### 3. Upload a File

```bash
curl -X POST http://localhost:8501/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/document.pdf"
```

### 4. Extract Text from Document

```bash
curl -X POST http://localhost:8501/api/v1/documents/FILE_ID/extract \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:
```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-here",
    "status": "pending",
    "progress": 0
  }
}
```

### 5. Check Task Status

```bash
curl -X GET http://localhost:8501/api/v1/tasks/TASK_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-here",
    "task_type": "extract",
    "status": "completed",
    "progress": 100,
    "result": {
      "text": "Extracted text...",
      "sections": ["Section 1", "Section 2"],
      "metadata": {
        "page_count": 10,
        "word_count": 5000,
        "language": "en"
      }
    }
  }
}
```

## Project Structure

```
backend/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API route handlers
│   │   ├── deps.py            # Dependencies (auth, db)
│   │   ├── errors.py          # Exception handlers
│   │   └── routers/           # Route modules
│   │       ├── auth.py
│   │       ├── files.py
│   │       ├── documents.py
│   │       ├── tasks.py
│   │       ├── users.py
│   │       └── statistics.py
│   ├── core/                  # Core functionality
│   │   ├── config.py          # Configuration
│   │   ├── security.py        # Auth & security
│   │   └── logger.py          # Logging
│   ├── db/                    # Database
│   │   ├── database.py        # DB connection
│   │   ├── session.py         # Session management
│   │   └── models/            # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   │   ├── user.py
│   │   ├── file.py
│   │   ├── task.py
│   │   └── document.py
│   ├── services/              # Business logic
│   │   ├── auth_service.py
│   │   ├── file_service.py
│   │   ├── llm_service.py
│   │   └── task_service.py
│   └── queue/                 # Task queue
│       ├── task_queue.py
│       └── tasks.py
└── tests/                     # Tests
    ├── contract/              # API contract tests
    ├── integration/           # Integration tests
    └── unit/                  # Unit tests
```

## Testing

### Run All Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Contract tests
pytest tests/contract/ -v

# All tests with coverage
pytest --cov=backend.src --cov-report=html
```

### Test Specific Module

```bash
pytest tests/unit/test_auth_service.py -v
```

## Development Workflow

### 1. Making Changes

1. Create a new branch from `001-fastapi-backend`
2. Implement your changes following the architecture
3. Write tests for new functionality
4. Run the test suite: `pytest`
5. Update API documentation if needed
6. Submit a pull request

### 2. Adding a New Endpoint

1. Create Pydantic schema in `schemas/`
2. Add SQLAlchemy model in `db/models/`
3. Implement service logic in `services/`
4. Create route handler in `api/routers/`
5. Register router in `main.py`
6. Add tests in `tests/`

### 3. Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Common Issues

### 1. Redis Connection Error

**Error**: `redis.exceptions.ConnectionError`

**Solution**: Ensure Redis is running
```bash
redis-cli ping
# Should return: PONG
```

### 2. Database Locked Error

**Error**: `sqlite3.OperationalError: database is locked`

**Solution**: Close all connections to the database
```bash
# Restart the application
pkill -f uvicorn
uvicorn backend.src.main:app --reload
```

### 3. Import Errors

**Error**: `ModuleNotFoundError`

**Solution**: Ensure PYTHONPATH includes the project root
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Production Deployment

### Using Docker

```dockerfile
# See Dockerfile in project root
docker build -t literature-assistant-api .
docker run -p 8501:8501 -e DASHSCOPE_API_KEY=your_key literature-assistant-api
```

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f worker
```

### Environment Variables for Production

```bash
# Set secure values
export SECRET_KEY=$(openssl rand -hex 32)
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
export DEBUG=False
export LOG_LEVEL=INFO
```

## Performance Optimization

### 1. Database Connection Pooling

Configure in `db/database.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)
```

### 2. Caching

Use Redis for caching frequently accessed data:
```python
from functools import lru_cache
from redis import asyncio as redis

redis_client = redis.Redis()

@cache.cached(timeout=300)
async def get_user_profile(user_id: str):
    # Cache for 5 minutes
    return await redis_client.get(f"user:{user_id}")
```

### 3. Async Optimization

- Use async/await throughout
- Avoid blocking operations
- Use connection pooling
- Implement proper error handling

## Monitoring & Logging

### Enable Access Logs

```python
# In main.py
from fastapi import Request
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.2f}s")
    return response
```

### Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    # Check database
    await database.execute("SELECT 1")

    # Check Redis
    redis_client.ping()

    return {"status": "healthy", "version": "1.0.0"}
```

## Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [RQ Documentation](https://python-rq.org/)
- [DashScope API](https://help.aliyun.com/zh/model-studio/developer-reference/overview)

## Support

For issues and questions:
- Check the API documentation: http://localhost:8501/docs
- Review existing tests in `tests/`
- Consult the project README.md