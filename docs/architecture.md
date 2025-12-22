# LLM App Architecture Documentation

## Overview

This document describes the architecture of the LLM App, an AI-powered literature reading assistant built with Python and Streamlit.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Modules](#core-modules)
3. [Data Flow](#data-flow)
4. [Database Schema](#database-schema)
5. [API Layer](#api-layer)
6. [Task Queue System](#task-queue-system)
7. [Security Considerations](#security-considerations)
8. [Deployment Architecture](#deployment-architecture)

## System Architecture

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────┐
│                        Presentation Layer                     │
│  (Streamlit UI)                                         │
├─────────────────────────────────────────────────────────────┤
│                      Business Logic Layer                     │
│  ┌───────────┬─────────────┬──────────────┬──────────┐  │
│  │   Auth    │   File      │   Text       │ Optimizer│  │
│  │  Manager  │  Handler    │  Processor   │          │  │
│  └───────────┴─────────────┴──────────────┴──────────┘  │
├─────────────────────────────────────────────────────────────┤
│                       API Layer                               │
│                (LLM Client Abstraction)                    │
├─────────────────────────────────────────────────────────────┤
│                    Data Access Layer                          │
│                (Database Manager)                          │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                       │
│  ┌──────────┬─────────────┬──────────────┬──────────┐  │
│  │  SQLite  │   Redis     │  File System │ RQ Worker│  │
│  │Database  │    Queue    │              │          │  │
│  └──────────┴─────────────┴──────────────┴──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Core Modules

### 1. Database Manager (`src/llm_app/core/database.py`)

**Purpose**: Centralized database operations

**Responsibilities**:
- User management (CRUD operations)
- File metadata storage
- Content caching
- Token-based authentication
- Task status tracking

**Key Features**:
- SQLite-based storage
- Connection management
- Index optimization
- Data integrity checks

### 2. Auth Manager (`src/llm_app/core/auth.py`)

**Purpose**: User authentication and authorization

**Responsibilities**:
- User registration
- Password hashing (SHA-256)
- Token generation and validation
- Session management

**Security Features**:
- Secure password hashing
- Token expiration (24 hours)
- UUID-based user identification

### 3. File Handler (`src/llm_app/core/file_handler.py`)

**Purpose**: File upload, processing, and storage

**Responsibilities**:
- File validation
- MD5-based deduplication
- Text extraction (PDF, DOC, DOCX, TXT)
- File storage management

**Key Features**:
- Multiple format support via textract
- Deduplication based on content hash
- Secure file naming (UUID-based)

### 4. Text Processor (`src/llm_app/core/text_processor.py`)

**Purpose**: Text analysis and processing

**Responsibilities**:
- Key text extraction from papers
- Summary generation
- Mind map creation
- Interactive Q&A

**Features**:
- LLM-powered content analysis
- Structured output (JSON)
- Result caching

### 5. Text Optimizer (`src/llm_app/core/optimizer.py`)

**Purpose**: Text improvement and transformation

**Capabilities**:
- Text optimization
- Paraphrasing
- Translation
- Clarity improvement
- Academic style enhancement
- Content expansion/summarization

### 6. LLM Client (`src/llm_app/api/llm_client.py`)

**Purpose**: Unified LLM API interface

**Supported APIs**:
- DashScope (Alibaba Cloud)
- OpenAI-compatible APIs

**Features**:
- Automatic retries
- Error handling
- Streaming support
- Response parsing

## Data Flow

### User Registration Flow

```
User Input → Auth Manager → Database Manager → Token Generation
     ↓
Session State Updated
```

### File Upload Flow

```
File Upload → File Handler → MD5 Calculation → Duplicate Check
     ↓
File Storage → Database Update → Return Success
```

### Text Processing Flow

```
User Request → Text Processor → LLM Client → Content Generation
     ↓
Database Storage → UI Display
```

### Async Task Flow

```
Task Creation → RQ Queue → Worker Process → Database Update
     ↓
Status Monitoring → UI Notification
```

## Database Schema

### Tables Overview

```sql
-- Users table
users (
    uuid TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    api_key TEXT,
    model_name TEXT DEFAULT 'qwen-max'
)

-- Files table
files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT NOT NULL,
    uid TEXT NOT NULL,
    md5 TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uuid TEXT NOT NULL,
    created_at TEXT
)

-- Contents table
contents (
    uid TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_extraction TEXT,
    file_mindmap TEXT,
    file_summary TEXT
)

-- Tokens table
tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
)

-- Task status table
task_status (
    task_id TEXT PRIMARY KEY,
    uid TEXT NOT NULL,
    content_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    job_id TEXT
)
```

## API Layer

### LLM Client Interface

```python
class LLMClient:
    def __init__(self, api_key: str, model_name: str, base_url: str)
    def chat_completion(self, messages: List[Dict]) -> str
    def extract_text_from_paper(self, content: str) -> Dict
    def generate_paper_summary(self, content: str) -> str
    def answer_question(self, content: str, question: str) -> str
    def optimize_text(self, text: str) -> str
    def generate_mindmap_data(self, text: str) -> Dict
```

### Supported Operations

1. **Text Extraction**: Categorize key content into research background, purpose, methods, results, and future work
2. **Summarization**: Generate concise summaries of academic papers
3. **Q&A**: Interactive question-answering about paper content
4. **Text Optimization**: Improve clarity, reduce similarity, enhance style
5. **Mind Map Generation**: Create visual representations of paper structure

## Task Queue System

### Architecture

```
┌─────────────┐
│   Main App  │  (Enqueues tasks)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Redis      │  (Task queue)
│   Queue     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RQ Worker  │  (Processes tasks)
│  (Background)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Database   │  (Stores results)
└─────────────┘
```

### Task Types

1. **Text Extraction**: Extract and categorize text from uploaded papers
2. **Summary Generation**: Generate summaries of papers
3. **Mind Map Creation**: Create visual mind maps

### Task Lifecycle

```
PENDING → QUEUED → STARTED → FINISHED
                ↓
              FAILED
```

## Security Considerations

### Authentication & Authorization

- Token-based authentication (JWT-like)
- 24-hour token expiration
- Per-user API key isolation
- Password hashing (SHA-256)

### Data Protection

- No plaintext storage of API keys
- User data isolation
- File access control per user

### Input Validation

- File type validation
- MD5-based deduplication
- SQL injection prevention (parameterized queries)

### API Security

- Base URL configuration
- API key per user
- No hardcoded credentials

## Deployment Architecture

### Development Environment

```
Streamlit App (Port 8501)
      ↓
SQLite Database
      ↓
Local File Storage
```

### Production Environment (Docker)

```
┌─────────────────────────────────────┐
│         Streamlit Container          │
│                                     │
│  ┌─────────────┐ ┌──────────────┐  │
│  │  Main App   │ │  RQ Worker   │  │
│  └─────────────┘ └──────────────┘  │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────┐      ┌──────────┐
│  SQLite  │      │  Redis   │
│ Database │      │   Queue  │
└──────────┘      └──────────┘
      │                 │
      └────────┬────────┘
               ▼
      ┌─────────────────┐
      │  File Storage   │
      │   (Volume)      │
      └─────────────────┘
```

### Docker Compose Services

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
    volumes:
      - ./database.sqlite:/app/database.sqlite
      - ./uploads:/app/uploads
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
```

## Configuration

### Environment Variables

```bash
# API Configuration
DASHSCOPE_API_KEY=your_api_key_here

# Database Configuration
DATABASE_PATH=./database.sqlite

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Application Configuration
LOG_LEVEL=INFO
STREAMLIT_SERVER_PORT=8501
```

### Model Configuration

Default model: `qwen-max`

Supported models:
- `qwen-max` (default, best quality)
- `qwen-plus` (balanced performance)
- `qwen-turbo` (fastest)

## Performance Considerations

### Optimization Strategies

1. **Caching**: LLM responses cached in database
2. **Deduplication**: MD5-based file deduplication
3. **Async Processing**: RQ for long-running tasks
4. **Database Indexing**: Indexed on frequently queried fields

### Scalability

- **Horizontal Scaling**: Multiple app instances with shared Redis
- **Vertical Scaling**: Redis memory optimization for task queue
- **Database**: SQLite suitable for small-medium workloads

## Monitoring & Logging

### Log Types

1. **User Actions**: Login, file upload, task execution
2. **API Calls**: LLM API metrics (response time, status)
3. **Errors**: Detailed error tracking with context
4. **Tasks**: Task execution times and status

### Log Configuration

```python
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
```

## Future Enhancements

### Planned Improvements

1. **PostgreSQL Migration**: For better scalability
2. **Celery Integration**: Advanced task queue management
3. **Microservices**: Split into dedicated services
4. **API Rate Limiting**: Prevent API abuse
5. **Enhanced Security**: OAuth2, API key encryption
6. **Real-time Updates**: WebSocket for task progress

### Technical Debt

- Password hashing: Upgrade to bcrypt or Argon2
- API key storage: Add encryption at rest
- Error handling: More granular exception types
- Testing: Increase coverage to 80%+
- Documentation: API reference completion

## Contributing

When contributing to the codebase:

1. Follow PEP 8 style guidelines
2. Add type hints to all functions
3. Write comprehensive tests
4. Update documentation
5. Ensure all CI checks pass
6. Use pre-commit hooks before committing

## License

MIT License - See LICENSE file for details