"""
File model for uploaded documents
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    JSON,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from llm_app.db.database import Base


class File(Base):
    """File model for uploaded documents"""

    __tablename__ = "files"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String, nullable=False)
    filename = Column(String, nullable=False)  # UUID-based storage filename
    file_path = Column(String, nullable=False)
    file_ext = Column(String(10), nullable=False)  # .pdf, .docx, .txt
    file_size = Column(Integer, nullable=False)
    md5 = Column(String(32), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    user_uuid = Column(String, ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    processing_status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, processing, completed, failed
    tags = Column(JSON, nullable=True)  # Optional tags array
    extracted_text = Column(Text, nullable=True)  # Extracted text content
    word_count = Column(Integer, nullable=True)  # Word count of extracted text
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="files")
    content = relationship("Content", back_populates="file", uselist=False, cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<File(id={self.id}, original_filename={self.original_filename}, status={self.processing_status})>"

    @property
    def file_id(self) -> str:
        """Expose file ID with API-friendly name."""
        return str(self.id)

    @property
    def is_processed(self) -> bool:
        """Check if file has been processed"""
        return self.processing_status == "completed"

    @property
    def is_processing(self) -> bool:
        """Check if file is currently being processed"""
        return self.processing_status == "processing"


# Indexes for performance
Index("ix_files_user_uuid", File.user_uuid)
Index("ix_files_status", File.processing_status)
Index("ix_files_md5", File.md5)
