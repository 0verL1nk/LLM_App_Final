"""
Task model for async task processing
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from db.database import Base


class Task(Base):
    """Task model for async operations tracking"""

    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(
        String(20),
        nullable=False,
        index=True,
    )  # extract, summarize, qa, rewrite, mindmap
    user_uuid = Column(String, ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String, ForeignKey("files.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, processing, completed, failed, cancelled
    progress = Column(Integer, default=0, nullable=False)
    job_id = Column(String, nullable=True)  # RQ job ID
    result = Column(JSON, nullable=True)  # Task result data
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tasks")
    file = relationship("File", back_populates="tasks")

    def __repr__(self) -> str:
        return (
            f"<Task(task_id={self.task_id}, task_type={self.task_type}, "
            f"status={self.status}, progress={self.progress}%)>"
        )

    @property
    def is_running(self) -> bool:
        """Check if task is currently running"""
        return self.status == "processing"

    @property
    def is_completed(self) -> bool:
        """Check if task is completed"""
        return self.status in ["completed", "failed", "cancelled"]

    @property
    def is_successful(self) -> bool:
        """Check if task completed successfully"""
        return self.status == "completed"

    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None