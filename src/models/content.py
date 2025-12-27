"""
Content model for generated content (text extraction, summaries, mindmaps)
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from db.database import Base


class Content(Base):
    """Content model for generated content from files"""

    __tablename__ = "contents"

    uid = Column(String, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    file_path = Column(String, nullable=False)
    file_extraction = Column(Text, nullable=True)  # Extracted text content
    file_mindmap = Column(JSON, nullable=True)  # Mind map structure as JSON
    file_summary = Column(JSON, nullable=True)  # Summary data as JSON
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    file = relationship("File", back_populates="content")

    def __repr__(self) -> str:
        return f"<Content(uid={self.uid}, has_extraction={self.file_extraction is not None})>"

    @property
    def has_extraction(self) -> bool:
        """Check if text extraction exists"""
        return self.file_extraction is not None

    @property
    def has_mindmap(self) -> bool:
        """Check if mindmap exists"""
        return self.file_mindmap is not None

    @property
    def has_summary(self) -> bool:
        """Check if summary exists"""
        return self.file_summary is not None