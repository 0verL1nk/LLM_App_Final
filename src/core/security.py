"""
JWT token generation and validation utilities with Argon2 password hashing
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import jwt, JWTError
from argon2 import PasswordHasher
from argon2.low_level import Type
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status

from core.config import settings

# Argon2 password hasher (replaces bcrypt - no 72 byte limit, more secure)
pwd_hasher = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # Memory usage in KiB (64MB)
    parallelism=4,      # Number of parallel threads
    hash_len=32,        # Length of the hash in bytes
    salt_len=16,        # Length of the salt in bytes
    type=Type.ID        # Argon2id - best protection against side-channel and GPU attacks
)


# Keep pwd_context for backward compatibility but never use it
pwd_context = None  # Do not use - deprecated


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JWT access token

    Args:
        subject: User UUID or identifier
        expires_delta: Custom expiration time delta
        additional_claims: Additional claims to include in token

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.utcnow() + expires_delta

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
    }

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash using Argon2

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    try:
        pwd_hasher.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False
    except Exception as e:
        # Don't reveal details to prevent timing attacks
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using Argon2 (no 72 byte limit, more secure)

    Args:
        password: Plain text password (no length limit with Argon2)

    Returns:
        Hashed password string
    """
    return pwd_hasher.hash(password)


def verify_api_key(api_key: str) -> bool:
    """
    Verify a DashScope API key format

    Args:
        api_key: API key to verify

    Returns:
        True if format is valid, False otherwise
    """
    # Basic validation - DashScope API keys start with 'sk-'
    return api_key.startswith("sk-") and len(api_key) > 20
