"""
Authentication module for the LLM App.

This module provides authentication and authorization functionality
including login, registration, token management, and session handling.
"""

import uuid
from typing import Optional, Tuple

from .database import DatabaseManager


class AuthManager:
    """Authentication and authorization manager."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize auth manager.

        Args:
            db_manager: Database manager instance. Creates new one if None.
        """
        self.db = db_manager or DatabaseManager()

    def generate_uuid(self) -> str:
        """Generate a new UUID.

        Returns:
            String representation of a UUID
        """
        return str(uuid.uuid4())

    def register(self, username: str, password: str) -> Tuple[bool, str, str]:
        """Register a new user.

        Args:
            username: Username
            password: Password

        Returns:
            Tuple of (success, token, error_message)
            - success: True if registration successful
            - token: Authentication token if successful
            - error_message: Error message if failed
        """
        # Check if username exists
        if self.db.get_user_by_username(username):
            return False, "", "用户名已存在"

        # Generate UUID and create user
        user_uuid = self.generate_uuid()
        if not self.db.create_user(username, password, user_uuid):
            return False, "", "用户创建失败"

        # Generate and save token
        token = self.db.save_token(user_uuid)
        return True, token, ""

    def login(self, username: str, password: str) -> Tuple[bool, str, str]:
        """Login user.

        Args:
            username: Username
            password: Password

        Returns:
            Tuple of (success, token, error_message)
        """
        import hashlib

        # Get user by username
        user = self.db.get_user_by_username(username)
        if not user:
            return False, "", "账号密码错误"

        # Verify password
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if password_hash != user[2]:
            return False, "", "账号密码错误"

        # Generate and save token
        token = self.db.save_token(user[0])
        return True, token, ""

    def get_uuid_by_token(self, token: str) -> Optional[str]:
        """Get user UUID by token.

        Args:
            token: Authentication token

        Returns:
            User UUID if token valid, None otherwise
        """
        return self.db.get_uuid_by_token(token)

    def is_token_valid(self, token: str) -> bool:
        """Check if token is valid.

        Args:
            token: Authentication token

        Returns:
            True if valid, False otherwise
        """
        return not self.db.is_token_expired(token)

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired.

        Args:
            token: Authentication token

        Returns:
            True if expired, False otherwise
        """
        return self.db.is_token_expired(token)
