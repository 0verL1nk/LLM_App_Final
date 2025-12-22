# API Reference

## Core Modules

### DatabaseManager

Manages all database operations including users, files, contents, and tokens.

#### Class: `DatabaseManager`

```python
class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None) -> None
```

##### Methods

**Database Initialization**

```python
def init_database(self) -> None:
    """Initialize all database tables."""
```

**File Operations**

```python
def save_file_to_database(
    self,
    original_filename: str,
    uid: str,
    uuid_value: str,
    md5_value: str,
    file_path: str,
    created_at: str
) -> None:
    """Save file metadata to database."""
```

```python
def get_user_files(self, uuid_value: str) -> List[Tuple[Any, ...]]:
    """Get all files for a user."""
```

```python
def get_uid_by_md5(self, md5_value: str) -> Optional[str]:
    """Get file UID by MD5 hash."""
```

```python
def check_file_exists(self, md5_value: str) -> bool:
    """Check if file with MD5 exists."""
```

**Content Operations**

```python
def save_content_to_database(
    self,
    uid: str,
    file_path: str,
    content: str,
    content_type: str
) -> None:
    """Save content to database."""
```

```python
def get_content_by_uid(
    self,
    uid: str,
    content_type: str
) -> Optional[str]:
    """Get content by UID."""
```

```python
def delete_content_by_uid(
    self,
    uid: str,
    content_type: str
) -> None:
    """Delete specific content by UID."""
```

**User Operations**

```python
def create_user(
    self,
    username: str,
    password: str,
    uuid_value: str
) -> bool:
    """Create a new user."""
```

```python
def get_user(self, uuid_value: str) -> Optional[Tuple[str, str, str, Optional[str], str]]:
    """Get user by UUID."""
```

```python
def get_user_by_username(self, username: str) -> Optional[Tuple[str, str, str, Optional[str], str]]:
    """Get user by username."""
```

```python
def update_user_api_key(self, uuid_value: str, api_key: str) -> None:
    """Update user's API key."""
```

```python
def get_user_api_key(self, uuid_value: str) -> Optional[str]:
    """Get user's API key."""
```

```python
def get_user_model_name(self, uuid_value: str) -> str:
    """Get user's preferred model name."""
```

**Token Operations**

```python
def save_token(self, user_id: str) -> str:
    """Save token for user."""
```

```python
def get_uuid_by_token(self, token: str) -> Optional[str]:
    """Get UUID by token."""
```

```python
def is_token_expired(self, token: str) -> bool:
    """Check if token is expired."""
```

### AuthManager

Handles user authentication and authorization.

#### Class: `AuthManager`

```python
class AuthManager:
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None
```

##### Methods

```python
def generate_uuid(self) -> str:
    """Generate a new UUID."""
```

```python
def register(
    self,
    username: str,
    password: str
) -> Tuple[bool, str, str]:
    """Register a new user.

    Returns:
        Tuple of (success, token, error_message)
    """
```

```python
def login(
    self,
    username: str,
    password: str
) -> Tuple[bool, str, str]:
    """Login user.

    Returns:
        Tuple of (success, token, error_message)
    """
```

```python
def get_uuid_by_token(self, token: str) -> Optional[str]:
    """Get user UUID by token."""
```

```python
def is_token_valid(self, token: str) -> bool:
    """Check if token is valid."""
```

```python
def is_token_expired(self, token: str) -> bool:
    """Check if token is expired."""
```

### FileHandler

Manages file uploads, processing, and storage.

#### Class: `FileHandler`

```python
class FileHandler:
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None
```

##### Methods

```python
@staticmethod
def calculate_md5(file) -> str:
    """Calculate MD5 hash of uploaded file."""
```

```python
def get_file_uid(self, md5_value: str) -> str:
    """Get file UID for given MD5."""
```

```python
def save_uploaded_file(
    self,
    uploaded_file,
    uuid_value: str,
    save_dir: str
) -> Dict[str, str]:
    """Save uploaded file to storage and database.

    Returns:
        Dictionary with file information
    """
```

```python
@staticmethod
def extract_text(file_path: str) -> Dict[str, str]:
    """Extract text from file.

    Returns:
        Dictionary with result and text
        - result: 1 for success, -1 for failure
        - text: Extracted text or error message
    """
```

```python
def process_uploaded_file(
    self,
    uploaded_file,
    uuid_value: str
) -> Tuple[bool, str, Dict[str, str]]:
    """Process uploaded file (save and extract text).

    Returns:
        Tuple of (success, message, file_info_dict)
    """
```

```python
def get_user_files(self, uuid_value: str) -> list:
    """Get all files for a user."""
```

### LLMClient

Unified interface for LLM API interactions.

#### Class: `LLMClient`

```python
class LLMClient:
    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> None
```

##### Methods

```python
def chat_completion(
    self,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Union[str, Any]:
    """Send chat completion request."""
```

```python
def stream_completion(
    self,
    messages: List[Dict[str, str]],
    temperature: float = 0.7
):
    """Send streaming chat completion request."""
```

```python
def extract_text_from_paper(
    self,
    file_content: str
) -> Dict[str, Any]:
    """Extract and categorize key text from academic paper.

    Returns:
        Dictionary with categorized key text
    """
```

```python
def generate_paper_summary(self, file_content: str) -> str:
    """Generate summary of academic paper."""
```

```python
def answer_question(
    self,
    file_content: str,
    question: str
) -> str:
    """Answer question about paper content."""
```

```python
def optimize_text(self, text: str) -> str:
    """Optimize and paraphrase text."""
```

```python
def generate_mindmap_data(self, text: str) -> Dict[str, Any]:
    """Generate mindmap data from text content.

    Returns:
        Mindmap data in JSON format
    """
```

```python
def translate_text(
    self,
    text: str,
    target_language: str = "English"
) -> str:
    """Translate text to target language."""
```

### TextProcessor

Text extraction, analysis, and processing.

#### Class: `TextProcessor`

```python
class TextProcessor:
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        file_handler: Optional[FileHandler] = None,
        llm_client: Optional[LLMClient] = None
    ) -> None
```

##### Methods

```python
def set_llm_client(self, llm_client: LLMClient) -> None:
    """Set LLM client."""
```

```python
def extract_text(self, file_path: str) -> Tuple[bool, str]:
    """Extract text from file.

    Returns:
        Tuple of (success, extracted_text)
    """
```

```python
def text_extraction(
    self,
    file_path: str,
    uid: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Extract and categorize text from paper.

    Returns:
        Tuple of (success, message, extracted_content)
    """
```

```python
def file_summary(
    self,
    file_path: str,
    uid: str
) -> Tuple[bool, str]:
    """Generate summary of file.

    Returns:
        Tuple of (success, summary_text)
    """
```

```python
def generate_mindmap(
    self,
    file_path: str,
    uid: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Generate mindmap data for file.

    Returns:
        Tuple of (success, message, mindmap_data)
    """
```

```python
def answer_question(
    self,
    file_path: str,
    question: str,
    uid: str
) -> Tuple[bool, str]:
    """Answer question about file content.

    Returns:
        Tuple of (success, answer)
    """
```

```python
def get_extracted_content(self, uid: str) -> Optional[Dict[str, Any]]:
    """Get extracted content by UID."""
```

```python
def get_summary(self, uid: str) -> Optional[str]:
    """Get summary by UID."""
```

```python
def get_mindmap(self, uid: str) -> Optional[Dict[str, Any]]:
    """Get mindmap data by UID."""
```

### TextOptimizer

Text optimization, paraphrasing, and enhancement.

#### Class: `TextOptimizer`

```python
class TextOptimizer:
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        llm_client: Optional[LLMClient] = None
    ) -> None
```

##### Methods

```python
def set_llm_client(self, llm_client: LLMClient) -> None:
    """Set LLM client."""
```

```python
def optimize_text(self, text: str) -> Tuple[bool, str]:
    """Optimize and paraphrase text.

    Returns:
        Tuple of (success, optimized_text)
    """
```

```python
def reduce_similarity(
    self,
    text: str,
    original_text: Optional[str] = None
) -> Tuple[bool, str]:
    """Reduce text similarity (paraphrase to avoid plagiarism).

    Returns:
        Tuple of (success, modified_text)
    """
```

```python
def translate_text(
    self,
    text: str,
    target_language: str = "English"
) -> Tuple[bool, str]:
    """Translate text to target language.

    Returns:
        Tuple of (success, translated_text)
    """
```

```python
def improve_clarity(self, text: str) -> Tuple[bool, str]:
    """Improve text clarity and readability.

    Returns:
        Tuple of (success, improved_text)
    """
```

```python
def enhance_academic_style(self, text: str) -> Tuple[bool, str]:
    """Enhance academic writing style.

    Returns:
        Tuple of (success, enhanced_text)
    """
```

```python
def expand_content(
    self,
    text: str,
    expansion_ratio: float = 1.5
) -> Tuple[bool, str]:
    """Expand text content while maintaining quality.

    Returns:
        Tuple of (success, expanded_text)
    """
```

```python
def summarize_content(
    self,
    text: str,
    target_length: int = 200
) -> Tuple[bool, str]:
    """Summarize text to target length.

    Returns:
        Tuple of (success, summarized_text)
    """
```

### TaskQueueManager

Asynchronous task queue management using RQ (Redis Queue).

#### Class: `TaskQueueManager`

```python
class TaskQueueManager:
    def __init__(self) -> None
```

##### Methods

```python
def init_task_table(self) -> None:
    """Initialize task status table."""
```

```python
def create_task(
    self,
    task_id: str,
    uid: str,
    content_type: str
) -> None:
    """Create a new task record."""
```

```python
def update_task_status(
    self,
    task_id: str,
    status: TaskStatus,
    job_id: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """Update task status."""
```

```python
def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status by ID."""
```

```python
def get_task_status_by_uid(
    self,
    uid: str,
    content_type: str
) -> Optional[Dict[str, Any]]:
    """Get latest task status by UID and content type."""
```

```python
def get_job_status(self, job_id: str) -> Optional[str]:
    """Get job status from RQ."""
```

```python
def enqueue_task(
    self,
    task_func,
    *args,
    job_timeout: str = '10m',
    **kwargs
) -> Optional[str]:
    """Enqueue task to RQ queue."""
```

```python
def is_queue_available(self) -> bool:
    """Check if Redis queue is available."""
```

## Configuration

### Config Class

Centralized configuration management.

#### Class Methods

```python
@classmethod
def ensure_directories(cls) -> None:
    """Create necessary directories if they don't exist."""
```

```python
@classmethod
def get_database_dir(cls) -> Path:
    """Get database directory path."""
```

```python
@classmethod
def get_uploads_dir(cls) -> Path:
    """Get uploads directory path."""
```

#### Configuration Properties

```python
# Database
DATABASE_PATH: str = './database.sqlite'

# File Storage
UPLOADS_DIR: str = './uploads'

# Redis
REDIS_HOST: str = 'localhost'
REDIS_PORT: int = 6379
REDIS_DB: int = 0
REDIS_PASSWORD: Optional[str] = None
REDIS_URL: str

# LLM API
DEFAULT_MODEL: str = 'qwen-max'
API_BASE_URL: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

# Application
TOKEN_EXPIRY_SECONDS: int = 86400  # 24 hours
MAX_FILE_SIZE_MB: int = 100
ALLOWED_EXTENSIONS: set[str] = {'.txt', '.doc', '.docx', '.pdf'}

# Logging
LOG_LEVEL: str = 'INFO'
LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

## Page Helpers

### Functions

```python
def check_api_key_configured() -> Tuple[bool, Optional[str]]:
    """Check if API key is configured for the user."""
```

```python
def start_async_task(
    uid: str,
    content_type: str,
    task_func: callable,
    *args: Any
) -> Optional[str]:
    """Start an asynchronous task."""
```

```python
def check_task_and_content(
    uid: str,
    content_type: str,
    auto_start: bool = False
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Check task status and content availability."""
```

```python
def display_task_status(
    task_status: str,
    error_message: Optional[str] = None,
    auto_refresh: bool = True
) -> None:
    """Display task status in the UI."""
```

```python
def print_contents(content: Dict[str, Any]) -> None:
    """Print formatted contents to Streamlit."""
```

```python
def show_sidebar_api_key_setting() -> None:
    """Display API key setting in sidebar."""
```

## Task Workers

### Functions

```python
def task_text_extraction(
    task_id: str,
    file_path: str,
    uid: str,
    user_uuid: str
) -> tuple[bool, str]:
    """Execute text extraction task asynchronously."""
```

```python
def task_file_summary(
    task_id: str,
    file_path: str,
    uid: str,
    user_uuid: str
) -> tuple[bool, str]:
    """Execute file summary task asynchronously."""
```

```python
def task_generate_mindmap(
    task_id: str,
    file_path: str,
    uid: str,
    user_uuid: str
) -> tuple[bool, str]:
    """Execute mindmap generation task asynchronously."""
```

## Enums

### TaskStatus

```python
class TaskStatus(Enum):
    PENDING = "pending"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    QUEUED = "queued"
```

## Type Definitions

### Common Tuples

```python
# User record
UserRecord = Tuple[str, str, str, Optional[str], str]
# (uuid, username, password, api_key, model_name)

# File record
FileRecord = Tuple[int, str, str, str, str, str, str]
# (id, original_filename, uid, md5, file_path, uuid, created_at)

# Task status dict
TaskStatusDict = Dict[str, Any]
# {
#     'task_id': str,
#     'uid': str,
#     'content_type': str,
#     'status': str,
#     'created_at': str,
#     'updated_at': str,
#     'error_message': Optional[str],
#     'job_id': Optional[str]
# }
```

## Usage Examples

### Basic Usage

```python
from src.llm_app.core.database import DatabaseManager
from src.llm_app.core.auth import AuthManager

# Initialize
db = DatabaseManager()
auth = AuthManager(db)

# Register user
success, token, error = auth.register('username', 'password')

# Login
success, token, error = auth.login('username', 'password')

# Get user UUID
uuid = auth.get_uuid_by_token(token)

# Save API key
db.update_user_api_key(uuid, 'your_api_key')
```

### File Processing

```python
from src.llm_app.core.file_handler import FileHandler

file_handler = FileHandler()

# Upload file
result = file_handler.save_uploaded_file(
    uploaded_file,
    user_uuid,
    '/path/to/uploads'
)

# Extract text
text_result = file_handler.extract_text(result['file_path'])
```

### Text Analysis

```python
from src.llm_app.core.text_processor import TextProcessor
from src.llm_app.api.llm_client import LLMClient

# Setup
text_processor = TextProcessor()
llm_client = LLMClient(api_key='your_key', model_name='qwen-max')
text_processor.set_llm_client(llm_client)

# Extract text
success, message, content = text_processor.text_extraction(
    file_path,
    uid
)

# Generate summary
success, summary = text_processor.file_summary(
    file_path,
    uid
)
```

### Async Task

```python
from src.llm_app.queue.task_queue import TaskQueueManager
from src.llm_app.queue.workers import task_text_extraction

task_manager = TaskQueueManager()

# Create task
task_id = 'task-123'
task_manager.create_task(task_id, uid, 'file_extraction')

# Enqueue task
job_id = task_manager.enqueue_task(
    task_text_extraction,
    task_id,
    file_path,
    uid,
    user_uuid
)
```

## Error Handling

All methods return tuples `(success, result)` or `(success, result, message)` where:

- `success`: Boolean indicating if operation succeeded
- `result`: Result data (content, summary, etc.)
- `message`: Optional message (error or success)

### Example

```python
success, text = text_processor.extract_text(file_path)

if not success:
    # Handle error
    print(f"Error: {text}")
else:
    # Process text
    print(f"Extracted: {text}")
```

## Logging

```python
from src.llm_app.core.logger import LoggerManager

logger = LoggerManager().get_logger(__name__)

# Log actions
logger.info("User uploaded file", extra={"user_id": uuid})

# Log errors
logger.error("File processing failed", exc_info=True)

# Log API calls
LoggerManager.log_api_call(
    endpoint="/chat/completions",
    model="qwen-max",
    response_time=1.5,
    status="success"
)
```

---

For more examples and advanced usage, see the [Architecture Documentation](architecture.md) and [Migration Guide](migration_guide.md).