# Migration Guide: v1.x → v2.0

## Overview

This guide helps you migrate from the old project structure (v1.x) to the new modular architecture (v2.0).

## What's Changed

### Major Changes

1. **Project Structure**: Migrated to standard `src/` layout
2. **Code Organization**: Split 990-line `utils/utils.py` into 10+ focused modules
3. **Type Safety**: Added 100% type hints throughout the codebase
4. **Testing**: Added comprehensive test suite with 70-80% coverage
5. **Code Quality**: Integrated Ruff, MyPy, pre-commit hooks, and CI/CD

### Breaking Changes

⚠️ **Important**: The following changes require action:

1. **Import Paths**: Old import paths have changed
2. **Module Names**: Some functions/classes have been reorganized
3. **Dependencies**: New development dependencies required

## Migration Paths

### Option 1: Quick Migration (Recommended)

Keep existing code and gradually migrate to new structure.

```python
# Old way (still works during transition)
from utils import DatabaseManager
from utils import AuthManager

# New way (recommended)
from src.llm_app.core.database import DatabaseManager
from src.llm_app.core.auth import AuthManager
```

### Option 2: Full Migration

Update all imports to use new structure.

## Old vs New Structure Comparison

### Old Structure (v1.x)

```
LLM_App_Final/
├── utils/
│   ├── utils.py          # 990 lines - everything!
│   ├── task_queue.py
│   ├── tasks.py
│   └── page_helpers.py
├── pages/
│   ├── 1_🤓_原文提取.py
│   └── ...
└── 文件中心.py
```

### New Structure (v2.0)

```
LLM_App_Final/
├── src/
│   └── llm_app/
│       ├── core/                 # Business logic
│       │   ├── database.py       # Database operations
│       │   ├── auth.py          # Authentication
│       │   ├── file_handler.py  # File processing
│       │   ├── text_processor.py # Text analysis
│       │   ├── optimizer.py     # Text optimization
│       │   └── logger.py        # Logging
│       ├── api/
│       │   └── llm_client.py    # LLM API client
│       ├── queue/
│       │   ├── task_queue.py    # Task queue management
│       │   └── workers.py       # Background workers
│       ├── ui/
│       │   └── page_helpers.py  # UI helpers
│       └── main.py              # App entry point
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
└── docs/                         # Documentation
```

## Detailed Migration Steps

### Step 1: Install Development Dependencies

```bash
# Using uv (recommended)
uv sync --all-extras --dev

# Using pip
pip install pytest pytest-cov ruff mypy pre-commit
```

### Step 2: Update Import Statements

#### Database Operations

**Old**:
```python
from utils.utils import init_database, get_user_files, save_content_to_database
```

**New**:
```python
from src.llm_app.core.database import DatabaseManager

# Initialize once
db = DatabaseManager()

# Use methods
db.init_database()
files = db.get_user_files(uuid)
db.save_content_to_database(uid, file_path, content, content_type)
```

#### Authentication

**Old**:
```python
from utils.utils import login, register, get_uuid_by_token, is_token_expired
```

**New**:
```python
from src.llm_app.core.auth import AuthManager

auth = AuthManager()
success, token, error = auth.login(username, password)
success, token, error = auth.register(username, password)
uuid = auth.get_uuid_by_token(token)
is_valid = auth.is_token_valid(token)
```

#### File Handling

**Old**:
```python
from utils.utils import extract_files, save_file_to_database, check_file_exists
```

**New**:
```python
from src.llm_app.core.file_handler import FileHandler

file_handler = FileHandler()
result = file_handler.extract_text(file_path)
file_info = file_handler.save_uploaded_file(uploaded_file, uuid, save_dir)
exists = file_handler.check_file_exists(md5)
```

#### Text Processing

**Old**:
```python
from utils.utils import text_extraction, file_summary, generate_mindmap_data
```

**New**:
```python
from src.llm_app.core.text_processor import TextProcessor
from src.llm_app.api.llm_client import LLMClient

# Setup
db = DatabaseManager()
text_processor = TextProcessor(db)
llm_client = LLMClient(api_key, model_name)
text_processor.set_llm_client(llm_client)

# Use
success, text = text_processor.extract_text(file_path)
success, summary = text_processor.file_summary(file_path, uid)
success, message, mindmap = text_processor.generate_mindmap(file_path, uid)
```

#### Task Queue

**Old**:
```python
from utils.task_queue import TaskStatus, create_task, enqueue_task
```

**New**:
```python
from src.llm_app.queue.task_queue import TaskQueueManager, TaskStatus

task_manager = TaskQueueManager()
task_manager.create_task(task_id, uid, content_type)
job_id = task_manager.enqueue_task(task_func, *args)
```

### Step 3: Update Function Calls

#### Old Database Functions → New Class Methods

| Old Function | New Method |
|-------------|------------|
| `init_database(db_name)` | `db.init_database()` |
| `get_user_files(uuid, db_name)` | `db.get_user_files(uuid)` |
| `save_content_to_database(uid, path, content, type)` | `db.save_content_to_database(uid, path, content, type)` |
| `get_api_key(uuid)` | `db.get_user_api_key(uuid)` |
| `update_user_api_key(uuid, key)` | `db.update_user_api_key(uuid, key)` |
| `save_token(user_id)` | `db.save_token(user_id)` |

#### Old Auth Functions → New AuthManager Methods

| Old Function | New Method |
|-------------|------------|
| `login(username, password)` | `auth.login(username, password)` |
| `register(username, password)` | `auth.register(username, password)` |
| `get_uuid_by_token(token)` | `auth.get_uuid_by_token(token)` |
| `is_token_expired(token)` | `auth.is_token_expired(token)` |

### Step 4: Update Page Files

#### Before (Old):

```python
# pages/1_🤓_原文提取.py
from utils.utils import check_api_key_configured, print_contents
from utils.page_helpers import (
    check_task_and_content,
    start_async_task,
    display_task_status
)
from utils.tasks import task_text_extraction
```

#### After (New):

```python
# src/pages/1_🤓_原文提取.py
from src.llm_app.core.database import DatabaseManager
from src.llm_app.core.auth import AuthManager
from src.llm_app.ui.page_helpers import (
    check_api_key_configured,
    check_task_and_content,
    start_async_task,
    display_task_status
)
from src.llm_app.queue.workers import task_text_extraction
```

### Step 5: Configuration Updates

#### Environment Variables

Add these to your `.env` or shell:

```bash
# New environment variables
DATABASE_PATH=./database.sqlite
UPLOADS_DIR=./uploads
LOG_LEVEL=INFO
```

#### Configuration Object

**Old**:
```python
# Globals scattered around
model_name = 'qwen-max'
```

**New**:
```python
from src.llm_app.config import Config

# Access configuration
model = Config.DEFAULT_MODEL
db_path = Config.DATABASE_PATH
```

### Step 6: Update Main Entry Point

#### Before (Old):

```bash
streamlit run 文件中心.py
```

#### After (New):

```bash
# Option 1: Using new main
streamlit run src/llm_app/main.py

# Option 2: Keep old entry point
streamlit run 文件中心.py  # Still works via compatibility layer
```

### Step 7: Install and Setup Pre-commit

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Step 8: Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/llm_app --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Step 9: Code Quality Checks

```bash
# Lint code
ruff check src/

# Format code
ruff format src/

# Type checking
mypy src/
```

## API Changes Summary

### Database Manager

```python
# Old API
init_database(db_path)
get_user_files(uuid, db_path)

# New API
db = DatabaseManager(db_path)
db.init_database()
db.get_user_files(uuid)
```

### Auth Manager

```python
# Old API
login(username, password, db_path)
register(username, password, db_path)

# New API
auth = AuthManager()
auth.login(username, password)
auth.register(username, password)
```

### LLM Client

```python
# Old API (implicit, via get_openai_client())
client = get_openai_client()

# New API (explicit)
from src.llm_app.api.llm_client import LLMClient
client = LLMClient(api_key, model_name)
```

## Compatibility Layer

⚠️ **Temporary**: During transition, a compatibility layer is provided.

```python
# This still works but shows deprecation warning
from utils import login, register

# Recommended to update to:
from src.llm_app.core.auth import AuthManager
```

The compatibility layer will be removed in **v3.0**.

## Testing Your Migration

### 1. Unit Tests

```bash
# Run database tests
pytest tests/unit/test_database.py -v

# Run auth tests
pytest tests/unit/test_auth.py -v

# Run file handler tests
pytest tests/unit/test_file_handler.py -v
```

### 2. Integration Tests

```bash
# Run complete flow test
pytest tests/integration/test_complete_flow.py -v
```

### 3. Manual Testing

1. Register a new user
2. Login and verify token
3. Upload a file
4. Run text extraction
5. Generate summary
6. Create mind map

## Common Issues and Solutions

### Issue 1: ImportError

**Problem**:
```python
ModuleNotFoundError: No module named 'src.llm_app'
```

**Solution**: Ensure you're running from project root and Python path includes `src/`

```bash
# Run from project root
cd /path/to/LLM_App_Final
streamlit run src/llm_app/main.py
```

### Issue 2: Database Path

**Problem**: Database not found or not initialized

**Solution**:
```python
from src.llm_app.core.database import DatabaseManager

# Explicitly set database path
db = DatabaseManager('/path/to/database.sqlite')
db.init_database()
```

### Issue 3: LLM Client Not Set

**Problem**: `LLM client not configured` error

**Solution**:
```python
from src.llm_app.core.text_processor import TextProcessor
from src.llm_app.api.llm_client import LLMClient

text_processor = TextProcessor()
llm_client = LLMClient(api_key, model_name)
text_processor.set_llm_client(llm_client)  # Important!
```

### Issue 4: Type Errors

**Problem**: MyPy type checking failures

**Solution**: Add proper type hints

```python
# Before
def process_file(file_path):
    return True

# After
def process_file(file_path: str) -> bool:
    return True
```

## Performance Improvements

### 1. Connection Reuse

**Old** (creates new connection each time):
```python
def get_user_files(uuid):
    conn = sqlite3.connect(db_path)
    # ...
```

**New** (reuses connection):
```python
db = DatabaseManager()  # Reuses connection
def get_user_files(uuid):
    return self.db.get_user_files(uuid)
```

### 2. Caching

Results are now cached in the database:

```python
# First call - hits LLM API
text_processor.text_extraction(file_path, uid)

# Second call - uses cached result
text_processor.text_extraction(file_path, uid)
```

### 3. Async Processing

Long-running tasks use RQ (Redis Queue):

```python
# Tasks run in background
task_id = start_async_task(uid, 'file_extraction', task_func, *args)
# UI shows progress
# User notified when complete
```

## Benefits of Migration

### For Developers

1. **Better IDE Support**: Autocomplete, go-to-definition
2. **Type Safety**: Catch bugs at development time
3. **Easier Testing**: Unit tests for each module
4. **Cleaner Code**: Single responsibility per module
5. **Better Documentation**: Docstrings for all functions

### For Users

1. **Faster Development**: Quicker bug fixes and features
2. **More Reliable**: Comprehensive test coverage
3. **Better Performance**: Optimized database queries
4. **Easier Deployment**: Docker and CI/CD support

## Next Steps

### Immediate (After Migration)

1. ✅ Run all tests: `pytest`
2. ✅ Check code quality: `ruff check src/`
3. ✅ Verify functionality manually
4. ✅ Update documentation

### Short Term (Next Sprint)

1. Increase test coverage to 80%+
2. Add more integration tests
3. Optimize slow queries
4. Add monitoring and logging

### Long Term (Future Versions)

1. PostgreSQL migration
2. Microservices split
3. Real-time updates (WebSockets)
4. Advanced caching strategies

## Getting Help

### Resources

- 📖 **Architecture Documentation**: `docs/architecture.md`
- 🧪 **Test Documentation**: `tests/README.md`
- 🔧 **Configuration Guide**: `docs/configuration.md`

### Support

- 📧 **Email**: team@llm-app.dev
- 💬 **Discussions**: GitHub Discussions
- 🐛 **Issues**: GitHub Issues
- 📖 **Wiki**: GitHub Wiki

## Changelog

### v2.0.0 (Major Update)

#### Added
- ✅ New `src/` layout structure
- ✅ 10+ focused modules with single responsibilities
- ✅ 100% type hints
- ✅ Comprehensive test suite (70-80% coverage)
- ✅ Ruff linting and formatting
- ✅ MyPy type checking
- ✅ Pre-commit hooks
- ✅ GitHub Actions CI/CD
- ✅ Docker support
- ✅ Architecture documentation
- ✅ Migration guide

#### Changed
- 🔄 All imports use new `src/llm_app` structure
- 🔄 Database operations use `DatabaseManager` class
- 🔄 Authentication uses `AuthManager` class
- 🔄 File handling uses `FileHandler` class
- 🔄 Text processing uses `TextProcessor` class

#### Removed
- ❌ Old flat directory structure
- ❌ Globals in `utils/utils.py`
- ❌ Mixed concerns in single files
- ❌ Manual testing process

---

## Summary Checklist

- [ ] Install development dependencies
- [ ] Update import statements
- [ ] Update function calls to use new classes
- [ ] Configure environment variables
- [ ] Install and run pre-commit hooks
- [ ] Run test suite
- [ ] Check code quality with Ruff and MyPy
- [ ] Test manually
- [ ] Update documentation
- [ ] Deploy to production

**Estimated Migration Time**: 2-4 hours for full migration

**Support**: If you encounter issues, please open an issue on GitHub with the "migration" label.