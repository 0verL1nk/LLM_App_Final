"""
User model for authentication and profile management
"""
import uuid as uuid_module
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship

from db.database import Base


class User(Base):
    """User model for authentication and profile"""

    __tablename__ = "users"

    # Use String for UUID to ensure SQLite compatibility
    uuid = Column(String, primary_key=True, default=lambda: str(uuid_module.uuid4()), unique=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    api_key = Column(Text, nullable=True)  # Optional per-user DashScope API key
    preferred_model = Column(String(100), default="qwen-max", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    statistics = relationship("Statistics", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(uuid={self.uuid}, username={self.username}, email={self.email})>"

    @property
    def user_id(self) -> str:
        """Get user ID as string"""
        return str(self.uuid)

    @property
    def has_api_key(self) -> bool:
        """Check if user has configured an API key"""
        return self.api_key is not None and len(self.api_key.strip()) > 0