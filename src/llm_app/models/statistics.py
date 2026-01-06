"""
Statistics model for usage metrics
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    Float,
    DateTime,
    String,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from llm_app.db.database import Base


class Statistics(Base):
    """Statistics model for aggregated usage metrics per user"""

    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uuid = Column(String, ForeignKey("users.uuid", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_files = Column(Integer, default=0, nullable=False)
    processed_files = Column(Integer, default=0, nullable=False)
    processing_files = Column(Integer, default=0, nullable=False)
    files_this_month = Column(Integer, default=0, nullable=False)
    total_api_calls = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    api_calls_this_month = Column(Integer, default=0, nullable=False)
    completed_tasks = Column(Integer, default=0, nullable=False)
    pending_tasks = Column(Integer, default=0, nullable=False)
    average_completion_time = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="statistics")

    def __repr__(self) -> str:
        return (
            f"<Statistics(user_uuid={self.user_uuid}, total_files={self.total_files}, "
            f"total_api_calls={self.total_api_calls})>"
        )

    @property
    def success_rate(self) -> float:
        """Calculate task success rate"""
        total_tasks = self.completed_tasks + self.pending_tasks
        if total_tasks == 0:
            return 0.0
        return (self.completed_tasks / total_tasks) * 100