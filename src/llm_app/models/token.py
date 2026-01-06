"""
Token model for JWT authentication
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from llm_app.db.database import Base


class Token(Base):
    """Token model for JWT authentication"""

    __tablename__ = "tokens"

    token = Column(String, primary_key=True, unique=True)
    user_uuid = Column(String, ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tokens")

    def __repr__(self) -> str:
        return f"<Token(token={self.token}, user_uuid={self.user_uuid}, expires_at={self.expires_at})>"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)"""
        return not self.is_expired and not self.revoked