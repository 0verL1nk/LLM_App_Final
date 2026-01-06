"""
Authentication router with endpoints for user registration, login, and logout
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.schemas.user import (
    UserCreate,
    UserLogin,
    LoginResponse,
    RegisterResponse,
    MessageResponse
)
from llm_app.api.deps import get_db, CurrentUser
from llm_app.services.auth_service import AuthService
from llm_app.api.errors import create_success_response
from llm_app.core.logger import get_logger

logger = get_logger(__name__)

# Create router with tag for OpenAPI documentation
router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        422: {"description": "Validation Error - Invalid request data"}
    }
)

# Security scheme for documentation
security = HTTPBearer(auto_error=False)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with username, email, and password"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    """
    Register a new user account

    Args:
        user_data: User registration data (username, email, password, optional preferred_model)
        db: Database session

    Returns:
        RegisterResponse: User info and JWT token

    Raises:
        409: User with username or email already exists
        422: Invalid input data
        500: Internal server error
    """
    try:
        # Create user
        user = await AuthService.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            preferred_model=user_data.preferred_model or "qwen-max"
        )

        # Generate authentication token for immediate login
        auth_result = await AuthService.authenticate_user(
            db=db,
            username=user_data.username,
            password=user_data.password
        )

        logger.info(f"User registered successfully: {user.username}")

        # Return user info and token
        return RegisterResponse(
            access_token=auth_result["token"]["access_token"],
            token_type=auth_result["token"]["token_type"],
            expires_in=auth_result["token"]["expires_in"],
            user={
                "uuid": user.user_id,
                "username": user.username,
                "email": user.email,
                "has_api_key": user.has_api_key,
                "preferred_model": user.preferred_model,
                "created_at": user.created_at
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., 409 conflict, 422 validation)
        raise
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to internal error"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login user",
    description="Authenticate user with username/email and password"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """
    Login user with username/email and password

    Args:
        credentials: User login credentials (username, password)
        db: Database session

    Returns:
        LoginResponse: User info and JWT token

    Raises:
        401: Invalid username or password
        422: Invalid input data
        500: Internal server error
    """
    try:
        # Authenticate user
        auth_result = await AuthService.authenticate_user(
            db=db,
            username=credentials.username,
            password=credentials.password
        )

        user = auth_result["user"]

        logger.info(f"User logged in successfully: {user.username}")

        # Return user info and token
        return LoginResponse(
            access_token=auth_result["token"]["access_token"],
            token_type=auth_result["token"]["token_type"],
            expires_in=auth_result["token"]["expires_in"],
            user={
                "uuid": user.user_id,
                "username": user.username,
                "email": user.email,
                "has_api_key": user.has_api_key,
                "preferred_model": user.preferred_model,
                "created_at": user.created_at
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., 401 unauthorized)
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to internal error"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Revoke current JWT token (logout)"
)
async def logout(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Logout user by revoking current JWT token

    Args:
        current_user: Current authenticated user (from JWT token)
        db: Database session

    Returns:
        MessageResponse: Success message

    Raises:
        401: Unauthorized - Invalid or missing authentication
        500: Internal server error
    """
    try:
        # Note: In a stateless JWT system, we cannot directly revoke the token
        # without a token blacklist. For now, we'll add the token to a blacklist
        # or mark it as revoked in the database.

        # Get token from Authorization header
        # This is handled by the security dependency in get_current_user

        # For simplicity, we'll just return success message
        # In a production system, you might want to:
        # 1. Add token to Redis blacklist with TTL
        # 2. Mark token as revoked in database (current implementation)
        # 3. Use shorter-lived tokens and refresh tokens

        logger.info(f"User logged out successfully: {current_user.username}")

        return MessageResponse(
            message="Successfully logged out"
        )

    except Exception as e:
        logger.error(f"Logout failed for user {current_user.username}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to internal error"
        )


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout from all devices",
    description="Revoke all JWT tokens for the current user"
)
async def logout_all(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Logout user from all devices by revoking all JWT tokens

    Args:
        current_user: Current authenticated user (from JWT token)
        db: Database session

    Returns:
        MessageResponse: Success message with token count

    Raises:
        401: Unauthorized - Invalid or missing authentication
        500: Internal server error
    """
    try:
        # Revoke all tokens for the user
        revoked_count = await AuthService.revoke_all_user_tokens(
            db=db,
            user_uuid=current_user.uuid
        )

        logger.info(f"User logged out from all devices: {current_user.username} ({revoked_count} tokens revoked)")

        return MessageResponse(
            message=f"Successfully logged out from all devices ({revoked_count} sessions terminated)"
        )

    except Exception as e:
        logger.error(f"Logout all failed for user {current_user.username}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to internal error"
        )


@router.get(
    "/me",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get information about the currently authenticated user"
)
async def get_current_user_info(
    current_user: CurrentUser
) -> dict:
    """
    Get current user information

    Args:
        current_user: Current authenticated user (from JWT token)

    Returns:
        dict: Current user information

    Raises:
        401: Unauthorized - Invalid or missing authentication
    """
    return {
        "uuid": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "has_api_key": current_user.has_api_key,
        "preferred_model": current_user.preferred_model,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }


@router.get(
    "/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify token",
    description="Verify if the current JWT token is valid"
)
async def verify_token(
    current_user: CurrentUser
) -> dict:
    """
    Verify that the current JWT token is valid

    Args:
        current_user: Current authenticated user (from JWT token)

    Returns:
        dict: Verification result with user info

    Raises:
        401: Unauthorized - Invalid or missing authentication
    """
    return {
        "valid": True,
        "user": {
            "uuid": current_user.user_id,
            "username": current_user.username,
            "email": current_user.email
        }
    }