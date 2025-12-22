"""
Unit tests for DatabaseManager.
"""

import pytest
import tempfile
from pathlib import Path

from src.llm_app.core.database import DatabaseManager


class TestDatabaseManager:
    """Test cases for DatabaseManager."""

    def test_init_database(self, temp_db):
        """Test database initialization."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Verify tables are created
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check files table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        )
        assert cursor.fetchone() is not None

        # Check contents table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contents'"
        )
        assert cursor.fetchone() is not None

        # Check users table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None

        # Check tokens table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'"
        )
        assert cursor.fetchone() is not None

        # Check task_status table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='task_status'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_save_and_get_user_files(self, temp_db, sample_file_data):
        """Test saving and retrieving user files."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Save file
        db.save_file_to_database(**sample_file_data)

        # Get files
        files = db.get_user_files(sample_file_data['uuid'])
        assert len(files) == 1
        assert files[0][1] == sample_file_data['original_filename']

    def test_get_uid_by_md5(self, temp_db, sample_file_data):
        """Test getting UID by MD5 hash."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Save file
        db.save_file_to_database(**sample_file_data)

        # Get UID
        uid = db.get_uid_by_md5(sample_file_data['md5'])
        assert uid == sample_file_data['uid']

    def test_check_file_exists(self, temp_db, sample_file_data):
        """Test checking if file exists by MD5."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # File doesn't exist initially
        assert not db.check_file_exists(sample_file_data['md5'])

        # Save file
        db.save_file_to_database(**sample_file_data)

        # File exists now
        assert db.check_file_exists(sample_file_data['md5'])

    def test_save_content_to_database(self, temp_db):
        """Test saving content to database."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        uid = 'test-uid-123'
        file_path = '/tmp/test.txt'
        content = '{"key": "value"}'
        content_type = 'file_extraction'

        # Save content
        db.save_content_to_database(uid, file_path, content, content_type)

        # Get content
        saved_content = db.get_content_by_uid(uid, content_type)
        assert saved_content == content

    def test_update_content(self, temp_db):
        """Test updating existing content."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        uid = 'test-uid-123'
        file_path = '/tmp/test.txt'

        # Save initial content
        db.save_content_to_database(uid, file_path, 'content1', 'file_extraction')

        # Update content
        db.save_content_to_database(uid, file_path, 'content2', 'file_extraction')

        # Get updated content
        saved_content = db.get_content_by_uid(uid, 'file_extraction')
        assert saved_content == 'content2'

    def test_create_user(self, temp_db, sample_user_data):
        """Test creating a new user."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        result = db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )
        assert result is True

        # Verify user exists
        user = db.get_user(sample_user_data['uuid'])
        assert user is not None
        assert user[1] == sample_user_data['username']

    def test_create_duplicate_user(self, temp_db, sample_user_data):
        """Test creating duplicate user fails."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user first time
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Try to create same user again
        result = db.create_user(
            sample_user_data['username'],
            'different_password',
            'different-uuid'
        )
        assert result is False

    def test_get_user_by_username(self, temp_db, sample_user_data):
        """Test getting user by username."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Get user by username
        user = db.get_user_by_username(sample_user_data['username'])
        assert user is not None
        assert user[0] == sample_user_data['uuid']

    def test_save_and_get_api_key(self, temp_db, sample_user_data):
        """Test saving and retrieving API key."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Save API key
        db.update_user_api_key(sample_user_data['uuid'], sample_user_data['api_key'])

        # Get API key
        api_key = db.get_user_api_key(sample_user_data['uuid'])
        assert api_key == sample_user_data['api_key']

    def test_get_user_model_name(self, temp_db, sample_user_data):
        """Test getting user's model name."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Get model name (should be default)
        model = db.get_user_model_name(sample_user_data['uuid'])
        assert model == 'qwen-max'

    def test_save_token(self, temp_db, sample_user_data):
        """Test saving authentication token."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Save token
        token = db.save_token(sample_user_data['uuid'])
        assert len(token) == 32

    def test_get_uuid_by_token(self, temp_db, sample_user_data):
        """Test getting UUID by token."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Save token
        token = db.save_token(sample_user_data['uuid'])

        # Get UUID by token
        retrieved_uuid = db.get_uuid_by_token(token)
        assert retrieved_uuid == sample_user_data['uuid']

    def test_is_token_expired(self, temp_db, sample_user_data):
        """Test token expiration check."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Save token
        token = db.save_token(sample_user_data['uuid'])

        # Token should not be expired initially
        assert not db.is_token_expired(token)

    def test_cleanup_expired_tokens(self, temp_db, sample_user_data):
        """Test cleanup of expired tokens."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create user
        db.create_user(
            sample_user_data['username'],
            sample_user_data['password'],
            sample_user_data['uuid']
        )

        # Manually create expired token
        import sqlite3
        import time
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        current_time = int(time.time())
        expired_time = current_time - 3600  # 1 hour ago
        cursor.execute(
            "INSERT INTO tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            ('expired_token', sample_user_data['uuid'], expired_time - 100, expired_time)
        )
        conn.commit()
        conn.close()

        # Cleanup expired tokens
        db._cleanup_expired_tokens()

        # Verify token is gone
        assert db.get_uuid_by_token('expired_token') is None

    def test_delete_content_by_uid(self, temp_db):
        """Test deleting specific content by UID."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        uid = 'test-uid-123'
        file_path = '/tmp/test.txt'
        content_type = 'file_extraction'

        # Save content
        db.save_content_to_database(uid, file_path, 'test content', content_type)

        # Verify content exists
        assert db.get_content_by_uid(uid, content_type) is not None

        # Delete content
        db.delete_content_by_uid(uid, content_type)

        # Content should be None
        assert db.get_content_by_uid(uid, content_type) is None