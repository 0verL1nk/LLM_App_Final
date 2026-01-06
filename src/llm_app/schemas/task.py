"""
Task-related Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Types of async tasks"""
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    QA = "qa"
    REWRITE = "rewrite"
    MINDMAP = "mindmap"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    file_id: str = Field(..., description="ID of the file to process")
    task_type: TaskType = Field(..., description="Type of task to execute")
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Task-specific options"
    )


class TaskStatusResponse(BaseModel):
    """Schema for task status response"""
    task_id: str = Field(..., description="Unique task identifier")
    file_id: str = Field(..., description="Associated file ID")
    task_type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(..., description="Current task status")
    progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Task result when completed"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Task completion timestamp"
    )


class TaskListItem(BaseModel):
    """Schema for task list item"""
    task_id: str
    file_id: str
    task_type: TaskType
    status: TaskStatus
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class TaskListResponse(BaseModel):
    """Schema for paginated task list response"""
    items: List[TaskListItem]
    pagination: Dict[str, int] = Field(
        ...,
        description="Pagination info: page, page_size, total, total_pages"
    )


class ExtractionResult(BaseModel):
    """Schema for text extraction result"""
    text: str = Field(..., description="Full extracted text")
    sections: List[str] = Field(
        default_factory=list,
        description="Text divided into sections"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata (page_count, word_count, language, etc.)"
    )


class ExtractionRequest(BaseModel):
    """Schema for extraction request options"""
    include_metadata: bool = Field(
        default=True,
        description="Whether to include document metadata"
    )
    split_sections: bool = Field(
        default=True,
        description="Whether to split text into sections"
    )
