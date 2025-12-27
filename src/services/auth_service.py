"""
Authentication service for user registration, login, and token management
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
from models.token import Token
from core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    verify_token
)
from core.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenNotFoundError,
    UserNotFoundError,
    DatabaseOperationError
)
from core.logger import get_logger

logger = get_logger(__name__)


def _coerce_uuid(value: str) -> str:
    """Ensure UUID values are properly formatted strings with hyphens."""
    if isinstance(value, uuid.UUID):
        return str(value)
    # Ensure string has proper UUID format with hyphens
    value_str = str(value).replace("-", "")
    if len(value_str) == 32:
        return f"{value_str[:8]}-{value_str[8:12]}-{value_str[12:16]}-{value_str[16:20]}-{value_str[20:]}"
    return str(value)


class AuthService:
    """Service class for authentication operations"""

    @staticmethod
    async def create_user(
        db: AsyncSession,
        username: str,
        email: str,
        password: str,
        preferred_model: str = "qwen-max"
    ) -> User:
        """
        Create a new user account

        Args:
            db: Database session
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            preferred_model: Preferred LLM model (default: qwen-max)

        Returns:
            Created User instance

        Raises:
            UserAlreadyExistsError: If username or email already exists
            DatabaseOperationError: If database operation fails
        """
        try:
            # Check if username already exists
            result = await db.execute(select(User).where(User.username == username))
            if result.scalar_one_or_none():
                raise UserAlreadyExistsError("username", username)

            # Check if email already exists
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise UserAlreadyExistsError("email", email)

            # Create new user
            logger.info(f"DEBUG: About to hash password for user {username}")
            hashed_password = get_password_hash(password)
            logger.info(f"DEBUG: Password hashed successfully, length={len(hashed_password)}")
            new_user = User(
                uuid=str(uuid.uuid4()),
                username=username,
                email=email,
                password=hashed_password,
                preferred_model=preferred_model,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            logger.info(f"User created successfully: {username} ({email})")
            return new_user

        except UserAlreadyExistsError:
            # Re-raise user already exists errors
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user {username}: {str(e)}")
            raise DatabaseOperationError(
                operation="create_user",
                error_message=str(e)
            )

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate a user with username/email and password

        Args:
            db: Database session
            username: Username or email address
            password: Plain text password

        Returns:
            Dict containing user info and token data

        Raises:
            InvalidCredentialsError: If username/email or password is invalid
            DatabaseOperationError: If database operation fails
        """
        try:
            # Try to find user by username first, then by email
            result = await db.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()

            if not user:
                # Try email lookup
                result = await db.execute(
                    select(User).where(User.email == username)
                )
                user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.password):
                logger.warning(f"Failed login attempt for username: {username}")
                raise InvalidCredentialsError()

            # Generate JWT token
            expires_delta = timedelta(hours=24)
            access_token = create_access_token(
                subject=str(user.uuid),
                expires_delta=expires_delta
            )

            # Calculate expiration timestamp
            expires_at = datetime.utcnow() + expires_delta

            # Store token in database
            token_record = Token(
                token=access_token,
                user_uuid=user.user_id,
                expires_at=expires_at,
                revoked=False,
                created_at=datetime.utcnow()
            )

            db.add(token_record)
            await db.commit()

            logger.info(f"User authenticated successfully: {user.username}")
            return {
                "user": user,
                "token": {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": int(expires_delta.total_seconds()),
                    "expires_at": expires_at
                }
            }

        except InvalidCredentialsError:
            # Re-raise authentication errors
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Authentication failed for {username}: {str(e)}")
            raise DatabaseOperationError(
                operation="authenticate_user",
                error_message=str(e)
            )

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_uuid: str
    ) -> Optional[User]:
        """
        Get user by UUID

        Args:
            db: Database session
            user_uuid: User UUID string

        Returns:
            User instance or None if not found

        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(User).where(User.uuid == _coerce_uuid(user_uuid))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user by ID {user_uuid}: {str(e)}")
            raise DatabaseOperationError(
                operation="get_user_by_id",
                error_message=str(e)
            )

    @staticmethod
    async def get_user_by_username(
        db: AsyncSession,
        username: str
    ) -> Optional[User]:
        """
        Get user by username

        Args:
            db: Database session
            username: Username string

        Returns:
            User instance or None if not found

        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {str(e)}")
            raise DatabaseOperationError(
                operation="get_user_by_username",
                error_message=str(e)
            )

    @staticmethod
    async def verify_token_validity(
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """
        Verify if a token is valid and return the associated user

        Args:
            db: Database session
            token: JWT token string

        Returns:
            User instance if token is valid, None otherwise

        Raises:
            TokenExpiredError: If token has expired
            TokenNotFoundError: If token is not in database or has been revoked
            DatabaseOperationError: If database operation fails
        """
        try:
            # First verify the JWT token signature and expiration
            payload = verify_token(token)

            # Then check if token exists in database and is not revoked
            result = await db.execute(
                select(Token)
                .where(Token.token == token)
                .where(Token.revoked == False)
            )
            token_record = result.scalar_one_or_none()

            if not token_record:
                raise TokenNotFoundError()

            # Check if token has expired
            if token_record.expires_at < datetime.utcnow():
                raise TokenExpiredError()

            # Get the user associated with this token
            result = await db.execute(
                select(User).where(User.uuid == _coerce_uuid(token_record.user_uuid))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundError(str(token_record.user_uuid))

            return user

        except TokenNotFoundError:
            # Re-raise token errors
            raise
        except TokenExpiredError:
            # Re-raise token errors
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise DatabaseOperationError(
                operation="verify_token_validity",
                error_message=str(e)
            )

    @staticmethod
    async def revoke_token(
        db: AsyncSession,
        token: str
    ) -> bool:
        """
        Revoke a token (logout)

        Args:
            db: Database session
            token: JWT token string to revoke

        Returns:
            True if token was revoked, False if not found

        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(Token).where(Token.token == token)
            )
            token_record = result.scalar_one_or_none()

            if not token_record:
                return False

            token_record.revoked = True
            await db.commit()

            logger.info(f"Token revoked successfully")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to revoke token: {str(e)}")
            raise DatabaseOperationError(
                operation="revoke_token",
                error_message=str(e)
            )

    @staticmethod
    async def revoke_all_user_tokens(
        db: AsyncSession,
        user_uuid: str
    ) -> int:
        """
        Revoke all tokens for a user

        Args:
            db: Database session
            user_uuid: User UUID string

        Returns:
            Number of tokens revoked

        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(Token).where(
                    Token.user_uuid == user_uuid,
                    Token.revoked == False
                )
            )
            tokens = result.scalars().all()

            revoked_count = 0
            for token_record in tokens:
                token_record.revoked = True
                revoked_count += 1

            await db.commit()

            logger.info(f"Revoked {revoked_count} tokens for user {user_uuid}")
            return revoked_count

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to revoke tokens for user {user_uuid}: {str(e)}")
            raise DatabaseOperationError(
                operation="revoke_all_user_tokens",
                error_message=str(e)
            )

    @staticmethod
    async def update_user_password(
        db: AsyncSession,
        user_uuid: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Update user password

        Args:
            db: Database session
            user_uuid: User UUID string
            current_password: Current password
            new_password: New password (will be hashed)

        Returns:
            True if password was updated

        Raises:
            InvalidCredentialsError: If current password is wrong
            UserNotFoundError: If user is not found
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(User).where(User.uuid == _coerce_uuid(user_uuid))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundError(user_uuid)

            # Verify current password
            if not verify_password(current_password, user.password):
                raise InvalidCredentialsError()

            # Update password
            user.password = get_password_hash(new_password)
            user.updated_at = datetime.utcnow()

            await db.commit()

            logger.info(f"Password updated successfully for user {user_uuid}")
            return True

        except (InvalidCredentialsError, UserNotFoundError):
            # Re-raise specific errors
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update password for user {user_uuid}: {str(e)}")
            raise DatabaseOperationError(
                operation="update_user_password",
                error_message=str(e)
            )

    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """
        Clean up expired tokens from database

        Args:
            db: Database session

        Returns:
            Number of tokens cleaned up

        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = await db.execute(
                select(Token).where(Token.expires_at < datetime.utcnow())
            )
            expired_tokens = result.scalars().all()

            count = len(expired_tokens)
            for token in expired_tokens:
                await db.delete(token)

            await db.commit()

            if count > 0:
                logger.info(f"Cleaned up {count} expired tokens")

            return count

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to cleanup expired tokens: {str(e)}")
            raise DatabaseOperationError(
                operation="cleanup_expired_tokens",
                error_message=str(e)
            )
