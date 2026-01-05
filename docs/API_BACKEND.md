# FastAPI Backend API Documentation

## Overview

The Literature Reading Assistant includes a FastAPI backend that provides RESTful APIs for all document processing features. This enables integration with other applications and frontend clients.

## Quick Start

### Running the API Server

```bash
# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Using Docker
cd deployment
docker-compose -f docker-compose.api.yml up -d
```

### API Documentation

Once running, access the interactive API docs:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## Authentication

All protected endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Getting a Token

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "email": "user1@example.com", "password": "password123"}'

# Login to get token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "password123"}'
```

## API Endpoints

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Register new user |
| POST | /auth/login | Login and get JWT token |
| POST | /auth/logout | Invalidate current token |

### Files (`/api/v1/files`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /files/upload | Upload a document (PDF, DOCX, TXT) |
| GET | /files | List user's files with pagination |
| GET | /files/{file_id} | Get file details |
| GET | /files/{file_id}/download | Download file |
| DELETE | /files/{file_id} | Delete file |

### Documents (`/api/v1/documents`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /documents/{file_id}/extract | Start text extraction task |
| GET | /documents/{file_id}/extraction | Get extraction result |
| POST | /documents/{file_id}/summarize | Generate document summary |
| POST | /documents/{file_id}/qa | Ask question about document |
| POST | /documents/{file_id}/rewrite | Rewrite text in different style |
| POST | /documents/{file_id}/mindmap | Generate mind map |

### Tasks (`/api/v1/tasks`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /tasks | List user's tasks with filtering |
| GET | /tasks/{task_id} | Get task status and result |
| POST | /tasks/{task_id}/cancel | Cancel a running task |

### Users (`/api/v1/users`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /users/me | Get current user profile |
| PUT | /users/api-key | Update DashScope API key |
| PUT | /users/preferences | Update user preferences |

### Statistics (`/api/v1/statistics`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /statistics | Get complete usage statistics |
| GET | /statistics/summary | Get quick statistics summary |
| GET | /statistics/files | Get file statistics only |
| GET | /statistics/tasks | Get task statistics only |

### WebSocket (`/api/v1/ws`)

| Endpoint | Description |
|----------|-------------|
| /ws/tasks?token=<jwt> | Real-time task status updates |

## Example Workflows

### Upload and Extract Text

```bash
# 1. Upload file
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf"

# Response: {"success": true, "data": {"file_id": "abc123", ...}}

# 2. Extract text
curl -X POST http://localhost:8000/api/v1/documents/abc123/extract \
  -H "Authorization: Bearer $TOKEN"

# Response: {"success": true, "data": {"task_id": "task456", ...}}

# 3. Check task status
curl http://localhost:8000/api/v1/tasks/task456 \
  -H "Authorization: Bearer $TOKEN"
```

### Generate Summary

```bash
curl -X POST http://localhost:8000/api/v1/documents/abc123/summarize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"summary_type": "detailed", "include_key_points": true}'
```

### Ask Questions

```bash
curl -X POST http://localhost:8000/api/v1/documents/abc123/qa \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main conclusion of this paper?"}'
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

| Endpoint | Limit |
|----------|-------|
| /auth/register | 5 requests / 5 minutes |
| /auth/login | 10 requests / minute |
| /files/upload | 20 requests / minute |
| Other endpoints | 100 requests / minute |

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `Retry-After`: Seconds until rate limit resets (when exceeded)

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": { "additional": "context" }
}
```

Common error codes:
- `AUTH_FAILED` - Authentication failed
- `AUTH_EXPIRED` - Token expired
- `FILE_NOT_FOUND` - File not found
- `FILE_TOO_LARGE` - File exceeds 50MB limit
- `FILE_TYPE_INVALID` - Unsupported file type
- `TASK_NOT_FOUND` - Task not found
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `VALIDATION_ERROR` - Request validation failed

## Docker Deployment

### API Only (Development)

```bash
cd deployment
docker-compose -f docker-compose.api.yml up -d
```

Services:
- API: http://localhost:8000
- Redis: localhost:6379

### Full Stack (Production)

```bash
cd deployment
docker-compose -f docker-compose.full.yml up -d
```

Services:
- FastAPI: http://localhost:8000
- Streamlit: http://localhost:8501
- Redis: localhost:6379
- RQ Worker: Background task processing

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DASHSCOPE_API_KEY | DashScope API key | Required |
| SECRET_KEY | JWT signing key | dev-secret-key |
| DATABASE_URL | Database connection string | sqlite+aiosqlite:///./database.sqlite |
| REDIS_HOST | Redis host | localhost |
| REDIS_PORT | Redis port | 6379 |
| DEBUG | Enable debug mode | false |

## Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "project": "Literature Reading Assistant",
  "checks": {
    "api": "healthy",
    "database": "healthy",
    "redis": "healthy"
  }
}
```

## WebSocket Integration

Connect to receive real-time task updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/tasks?token=YOUR_JWT_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'task_update') {
    console.log(`Task ${data.data.task_id}: ${data.data.status} (${data.data.progress}%)`);
  }
};

// Send ping to keep connection alive
setInterval(() => ws.send(JSON.stringify({type: 'ping'})), 30000);
```
