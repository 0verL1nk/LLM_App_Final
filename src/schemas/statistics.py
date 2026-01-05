"""
Statistics Pydantic schemas for usage metrics and monitoring.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FileStats(BaseModel):
    """Schema for file statistics"""

    total_files: int = Field(default=0, description="Total number of files uploaded")
    processed_files: int = Field(
        default=0, description="Number of files with completed processing"
    )
    processing_files: int = Field(
        default=0, description="Number of files currently being processed"
    )
    pending_files: int = Field(
        default=0, description="Number of files pending processing"
    )
    failed_files: int = Field(
        default=0, description="Number of files with failed processing"
    )
    files_this_month: int = Field(default=0, description="Files uploaded this month")
    total_size_bytes: int = Field(default=0, description="Total storage used in bytes")


class UsageStats(BaseModel):
    """Schema for API usage statistics"""

    total_api_calls: int = Field(default=0, description="Total API calls made")
    total_tokens: int = Field(default=0, description="Total tokens consumed")
    api_calls_this_month: int = Field(default=0, description="API calls this month")
    tokens_this_month: int = Field(default=0, description="Tokens consumed this month")
    average_response_time_ms: float = Field(
        default=0.0, description="Average API response time in milliseconds"
    )


class TaskStats(BaseModel):
    """Schema for task statistics"""

    total_tasks: int = Field(default=0, description="Total tasks created")
    completed_tasks: int = Field(default=0, description="Tasks completed successfully")
    pending_tasks: int = Field(default=0, description="Tasks currently pending")
    processing_tasks: int = Field(default=0, description="Tasks currently processing")
    failed_tasks: int = Field(default=0, description="Tasks that failed")
    cancelled_tasks: int = Field(default=0, description="Tasks that were cancelled")
    average_completion_time_seconds: float = Field(
        default=0.0, description="Average task completion time in seconds"
    )
    success_rate: float = Field(
        default=0.0, description="Task success rate as percentage"
    )


class TaskTypeBreakdown(BaseModel):
    """Schema for task breakdown by type"""

    extract: int = Field(default=0, description="Text extraction tasks")
    summarize: int = Field(default=0, description="Summarization tasks")
    qa: int = Field(default=0, description="Q&A tasks")
    rewrite: int = Field(default=0, description="Rewrite tasks")
    mindmap: int = Field(default=0, description="Mindmap generation tasks")


class StatisticsResponse(BaseModel):
    """Schema for complete statistics response"""

    user_uuid: str = Field(..., description="User UUID")
    file_stats: FileStats = Field(..., description="File statistics")
    usage_stats: UsageStats = Field(..., description="API usage statistics")
    task_stats: TaskStats = Field(..., description="Task statistics")
    task_breakdown: TaskTypeBreakdown = Field(..., description="Task breakdown by type")
    last_updated: datetime = Field(..., description="Last update timestamp")


class StatisticsSummary(BaseModel):
    """Schema for quick statistics summary"""

    total_files: int = Field(default=0, description="Total files")
    total_tasks: int = Field(default=0, description="Total tasks")
    completed_tasks: int = Field(default=0, description="Completed tasks")
    success_rate: float = Field(default=0.0, description="Success rate percentage")
