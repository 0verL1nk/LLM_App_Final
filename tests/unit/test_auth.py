"""
Unit tests for AuthManager.
"""

import pytest
import hashlib

from src.llm_app.core.auth import AuthManager
from src.llm_app.core.database import DatabaseManager


class TestAuthManager:
    """Test cases for AuthManager."""

    def test_init(self, temp_db):
        """Test initialization."""
        db = DatabaseManager(db_path=temp_db)
        auth = AuthManager(db_manager=db)
        assert auth.db == db

    def test_generate_uuid(self):
        """Test UUID generation."""
        auth = AuthManager()
        uuid1 = auth.generate_uuid()
        uuid2 = auth.generate_uuid()
        assert uuid1 != uuid2
        assert len(uuid1) == 36  # Standard UUID length

    def test_register_success(self, temp_db, sample_user_data):
        """Test successful user registration."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user
        success, token, error = auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success is True
        assert token is not None
        assert len(token) == 32
        assert error == ''

    def test_register_duplicate_username(self, temp_db, sample_user_data):
        """Test registration with duplicate username."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register first user
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        # Try to register with same username
        success, token, error = auth.register(
            sample_user_data['username'],
            'different_password'
        )

        assert success is False
        assert token == ''
        assert error == '用户名已存在'

    def test_login_success(self, temp_db, sample_user_data):
        """Test successful login."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user first
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        # Login
        success, token, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success is True
        assert token is not None
        assert len(token) == 32
        assert error == ''

    def test_login_wrong_password(self, temp_db, sample_user_data):
        """Test login with wrong password."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        # Try to login with wrong password
        success, token, error = auth.login(
            sample_user_data['username'],
            'wrong_password'
        )

        assert success is False
        assert token == ''
        assert error == '账号密码错误'

    def test_login_nonexistent_user(self, temp_db):
        """Test login with nonexistent user."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Try to login without registering
        success, token, error = auth.login('nonexistent', 'password')

        assert success is False
        assert token == ''
        assert error == '账号密码错误'

    def test_get_uuid_by_token(self, temp_db, sample_user_data):
        """Test getting UUID by token."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        # Login to get token
        success, token, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success is True

        # Get UUID by token
        uuid = auth.get_uuid_by_token(token)
        assert uuid is not None

    def test_get_uuid_by_invalid_token(self, temp_db):
        """Test getting UUID with invalid token."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Try with invalid token
        uuid = auth.get_uuid_by_token('invalid_token')
        assert uuid is None

    def test_is_token_valid(self, temp_db, sample_user_data):
        """Test token validity check."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register and login
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )
        success, token, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success is True

        # Check token validity
        assert auth.is_token_valid(token) is True

    def test_is_token_invalid(self, temp_db):
        """Test invalid token."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Check with non-existent token
        assert auth.is_token_valid('invalid_token') is False

    def test_is_token_expired(self, temp_db, sample_user_data):
        """Test token expiration check."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register and login
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )
        success, token, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success is True

        # Token should not be expired initially
        assert auth.is_token_expired(token) is False

    def test_multiple_registrations(self, temp_db):
        """Test multiple user registrations."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register multiple users
        users = [
            ('user1', 'pass1'),
            ('user2', 'pass2'),
            ('user3', 'pass3')
        ]

        tokens = []
        for username, password in users:
            success, token, error = auth.register(username, password)
            assert success is True
            tokens.append(token)

        # Verify all tokens are unique
        assert len(set(tokens)) == 3

    def test_login_after_logout(self, temp_db, sample_user_data):
        """Test login and token persistence."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register and login
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )
        success1, token1, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success1 is True

        # Login again (should get new token)
        success2, token2, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )

        assert success2 is True
        assert token1 != token2  # New token generated

    def test_password_hashing(self, temp_db, sample_user_data):
        """Test that passwords are properly hashed."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user
        auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )

        # Verify password is hashed in database
        user = db.get_user_by_username(sample_user_data['username'])
        assert user[2] != sample_user_data['password']  # Not stored in plain text
        assert user[2] == hashlib.sha256(
            sample_user_data['password'].encode('utf-8')
        ).hexdigest()

    def test_token_generation_randomness(self, temp_db, sample_user_data):
        """Test that tokens are randomly generated."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register and login multiple times
        tokens = []
        for _ in range(10):
            success, token, error = auth.register('user', 'pass')
            assert success is True
            tokens.append(token)

        # Verify all tokens are unique
        assert len(set(tokens)) == 10

    def test_auth_with_special_characters_in_username(self, temp_db):
        """Test authentication with special characters in username."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register with special characters
        special_username = 'user@example.com'
        success, token, error = auth.register(special_username, 'password123')
        assert success is True

        # Login with special characters
        success, token, error = auth.login(special_username, 'password123')
        assert success is True