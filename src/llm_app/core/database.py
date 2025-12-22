"""
Database management module for the LLM App.

This module provides a centralized database manager for all database operations
including users, files, contents, tokens, and tasks.
"""

import datetime
import hashlib
import logging
import sqlite3
from typing import Any, List, Optional, Tuple

from ..config import Config


class DatabaseManager:
    """Database manager for all database operations."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database manager.

        Args:
            db_path: Optional custom database path. Uses Config.DATABASE_PATH if None.
        """
        self.db_path = db_path or Config.DATABASE_PATH
        self.logger = logging.getLogger(__name__)
        self.init_database()

    def init_database(self) -> None:
        """Initialize all database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                uid TEXT NOT NULL,
                md5 TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uuid TEXT NOT NULL,
                created_at TEXT
            )
        """)

        # Create contents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                uid TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_extraction TEXT,
                file_mindmap TEXT,
                file_summary TEXT
            )
        """)

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uuid TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                api_key TEXT DEFAULT NULL,
                model_name TEXT DEFAULT 'qwen-max'
            )
        """)

        # Add model_name column if it doesn't exist
        try:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN model_name TEXT DEFAULT 'qwen-max'"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
        """)

        # Create index for tokens expiration
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_expires_at
            ON tokens(expires_at)
        """)

        conn.commit()
        conn.close()

        # Initialize task status table
        self._init_task_table()

    def _init_task_table(self) -> None:
        """Initialize task status table for RQ."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_status (
                task_id TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                content_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT,
                job_id TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status_uid
            ON task_status(uid, content_type)
        """)

        conn.commit()
        conn.close()

    # File operations
    def save_file_to_database(
        self,
        original_filename: str,
        uid: str,
        uuid_value: str,
        md5_value: str,
        file_path: str,
        created_at: str,
    ) -> None:
        """Save file metadata to database.

        Args:
            original_filename: Original name of the uploaded file
            uid: Unique file identifier
            uuid_value: User UUID
            md5_value: File MD5 hash for deduplication
            file_path: Path where file is stored
            created_at: Creation timestamp
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO files
            (original_filename, uid, md5, file_path, uuid, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (original_filename, uid, md5_value, file_path, uuid_value, created_at),
        )

        conn.commit()
        conn.close()

    def get_user_files(self, uuid_value: str) -> List[Tuple[Any, ...]]:
        """Get all files for a user.

        Args:
            uuid_value: User UUID

        Returns:
            List of file records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE uuid = ?", (uuid_value,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_uid_by_md5(self, md5_value: str) -> Optional[str]:
        """Get file UID by MD5 hash.

        Args:
            md5_value: MD5 hash of the file

        Returns:
            File UID if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM files WHERE md5 = ?", (md5_value,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def check_file_exists(self, md5_value: str) -> bool:
        """Check if file with MD5 exists.

        Args:
            md5_value: MD5 hash to check

        Returns:
            True if file exists, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM files WHERE md5 = ?", (md5_value,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    # Content operations
    def save_content_to_database(
        self, uid: str, file_path: str, content: str, content_type: str
    ) -> None:
        """Save content to database.

        Args:
            uid: File UID
            file_path: File path
            content: Content to save
            content_type: Type of content (e.g., 'file_extraction', 'file_summary')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if record exists
        cursor.execute("SELECT 1 FROM contents WHERE uid = ?", (uid,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing record
            cursor.execute(
                f"""
                UPDATE contents
                SET {content_type} = ?
                WHERE uid = ?
            """,
                (content, uid),
            )
        else:
            # Insert new record
            cursor.execute(
                f"""
                INSERT INTO contents (uid, file_path, {content_type})
                VALUES (?, ?, ?)
            """,
                (uid, file_path, content),
            )

        conn.commit()
        conn.close()

    def get_content_by_uid(self, uid: str, content_type: str) -> Optional[str]:
        """Get content by UID.

        Args:
            uid: File UID
            content_type: Type of content to retrieve

        Returns:
            Content string if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT {content_type} FROM contents WHERE uid = ?", (uid,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def delete_content_by_uid(self, uid: str, content_type: str) -> None:
        """Delete specific content by UID.

        Args:
            uid: File UID
            content_type: Type of content to delete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Set the content field to None
        cursor.execute(
            f"""
            UPDATE contents
            SET {content_type} = NULL
            WHERE uid = ?
        """,
            (uid,),
        )

        conn.commit()
        conn.close()

    # User operations
    def get_user(
        self, uuid_value: str
    ) -> Optional[Tuple[str, str, str, Optional[str], str]]:
        """Get user by UUID.

        Args:
            uuid_value: User UUID

        Returns:
            User tuple (uuid, username, password, api_key, model_name) or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE uuid = ?", (uuid_value,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_user_by_username(
        self, username: str
    ) -> Optional[Tuple[str, str, str, Optional[str], str]]:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User tuple or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        return result

    def create_user(self, username: str, password: str, uuid_value: str) -> bool:
        """Create a new user.

        Args:
            username: Username
            password: Password (will be hashed)
            uuid_value: User UUID

        Returns:
            True if successful, False if username exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if username exists
        if cursor.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone():
            conn.close()
            return False

        # Hash password
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        cursor.execute(
            """
            INSERT INTO users (uuid, username, password)
            VALUES (?, ?, ?)
        """,
            (uuid_value, username, password_hash),
        )

        conn.commit()
        conn.close()
        return True

    def update_user_api_key(self, uuid_value: str, api_key: str) -> None:
        """Update user's API key.

        Args:
            uuid_value: User UUID
            api_key: API key to save
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET api_key = ?
            WHERE uuid = ?
        """,
            (api_key, uuid_value),
        )
        conn.commit()
        conn.close()

    def get_user_api_key(self, uuid_value: str) -> Optional[str]:
        """Get user's API key.

        Args:
            uuid_value: User UUID

        Returns:
            API key if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT api_key FROM users WHERE uuid = ?", (uuid_value,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None

    def get_user_model_name(self, uuid_value: str) -> str:
        """Get user's preferred model name.

        Args:
            uuid_value: User UUID

        Returns:
            Model name (default: 'qwen-max')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT model_name FROM users WHERE uuid = ?", (uuid_value,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else Config.DEFAULT_MODEL

    # Token operations
    def save_token(self, user_id: str) -> str:
        """Save token for user.

        Args:
            user_id: User UUID

        Returns:
            Generated token
        """
        import random
        import string

        token = "".join(random.choice(string.ascii_letters) for _ in range(32))
        current_time = int(datetime.datetime.now().timestamp())
        expires_at = current_time + Config.TOKEN_EXPIRY_SECONDS

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tokens
            (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """,
            (token, user_id, current_time, expires_at),
        )

        conn.commit()
        conn.close()

        # Clean up expired tokens
        self._cleanup_expired_tokens()
        return token

    def get_uuid_by_token(self, token: str) -> Optional[str]:
        """Get UUID by token.

        Args:
            token: Authentication token

        Returns:
            User UUID if token is valid, None otherwise
        """
        # Check if token is expired
        if self.is_token_expired(token):
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id FROM tokens WHERE token = ?
        """,
            (token,),
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired.

        Args:
            token: Authentication token

        Returns:
            True if expired or not found, False otherwise
        """
        current_time = int(datetime.datetime.now().timestamp())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT expires_at FROM tokens WHERE token = ?
        """,
            (token,),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return True  # Token not found

        expires_at = result[0]
        if current_time >= expires_at:
            # Token expired, delete it
            self._delete_token(token)
            return True

        return False

    def _delete_token(self, token: str) -> None:
        """Delete token from database.

        Args:
            token: Token to delete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    def _cleanup_expired_tokens(self) -> None:
        """Clean up expired tokens."""
        current_time = int(datetime.datetime.now().timestamp())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE expires_at < ?", (current_time,))
        conn.commit()
        conn.close()
