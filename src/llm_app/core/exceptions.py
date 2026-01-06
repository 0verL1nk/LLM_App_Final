"""
Custom exceptions and error response models for the API
"""
from typing import Optional, Any, Dict
from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class APIException(HTTPException):
    """
    Custom exception class for API errors

    Args:
        status_code: HTTP status code
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Additional error details
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.details = details
        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                "details": details
            }
        )


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# Authentication Errors
class AuthenticationError(APIException):
    """Base class for authentication errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_FAILED",
            message=message,
            details=details
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when username or password is invalid"""

    def __init__(self):
        super().__init__(
            message="Invalid username or password",
            details={"reason": "credentials_mismatch"}
        )


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired"""

    def __init__(self):
        super().__init__(
            message="Authentication token has expired",
            details={"reason": "token_expired"}
        )


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid"""

    def __init__(self):
        super().__init__(
            message="Invalid authentication token",
            details={"reason": "token_invalid"}
        )


class TokenNotFoundError(AuthenticationError):
    """Raised when token is not found in database"""

    def __init__(self):
        super().__init__(
            message="Token not found or has been revoked",
            details={"reason": "token_not_found"}
        )


class UserNotFoundError(APIException):
    """Raised when user is not found"""

    def __init__(self, user_identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="USER_NOT_FOUND",
            message=f"User '{user_identifier}' not found",
            details={"user_identifier": user_identifier}
        )


class UserAlreadyExistsError(APIException):
    """Raised when attempting to create a user that already exists"""

    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="USER_ALREADY_EXISTS",
            message=f"User with {field} '{value}' already exists",
            details={"field": field, "value": value}
        )


# File Errors
class FileError(APIException):
    """Base class for file-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )


class FileNotFoundError(FileError):
    """Raised when file is not found"""

    def __init__(self, file_id: str):
        super().__init__(
            message=f"File with ID '{file_id}' not found",
            error_code="FILE_NOT_FOUND",
            details={"file_id": file_id}
        )


class FileTooLargeError(FileError):
    """Raised when file size exceeds limit"""

    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            message=f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)",
            error_code="FILE_TOO_LARGE",
            details={"file_size": file_size, "max_size": max_size}
        )


class InvalidFileTypeError(FileError):
    """Raised when file type is not allowed"""

    def __init__(self, file_extension: str, allowed_types: list):
        super().__init__(
            message=f"File type '.{file_extension}' is not allowed. Allowed types: {', '.join(allowed_types)}",
            error_code="FILE_TYPE_INVALID",
            details={"file_extension": file_extension, "allowed_types": allowed_types}
        )


class FileUploadError(FileError):
    """Raised when file upload fails"""

    def __init__(self, reason: str):
        super().__init__(
            message=f"File upload failed: {reason}",
            error_code="FILE_UPLOAD_FAILED",
            details={"reason": reason}
        )


# Task Errors
class TaskError(APIException):
    """Base class for task-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )


class TaskNotFoundError(TaskError):
    """Raised when task is not found"""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task with ID '{task_id}' not found",
            error_code="TASK_NOT_FOUND",
            details={"task_id": task_id}
        )


class TaskAlreadyExistsError(TaskError):
    """Raised when task with same type already exists for a file"""

    def __init__(self, file_id: str, task_type: str):
        super().__init__(
            message=f"Task of type '{task_type}' already exists for file '{file_id}'",
            error_code="TASK_ALREADY_EXISTS",
            details={"file_id": file_id, "task_type": task_type}
        )


class TaskExecutionError(TaskError):
    """Raised when task execution fails"""

    def __init__(self, task_id: str, error_message: str):
        super().__init__(
            message=f"Task execution failed: {error_message}",
            error_code="TASK_EXECUTION_FAILED",
            details={"task_id": task_id, "error": error_message}
        )


class TaskCancellationError(TaskError):
    """Raised when task cancellation fails"""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Cannot cancel task '{task_id}': task may already be completed or cancelled",
            error_code="TASK_CANCELLATION_FAILED",
            details={"task_id": task_id}
        )


# Content Errors
class ContentError(APIException):
    """Base class for content-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=message,
            details=details
        )


class ContentNotFoundError(ContentError):
    """Raised when content is not found"""

    def __init__(self, file_id: str, content_type: str):
        super().__init__(
            message=f"Content of type '{content_type}' not found for file '{file_id}'",
            error_code="CONTENT_NOT_FOUND",
            details={"file_id": file_id, "content_type": content_type}
        )


class ContentGenerationError(ContentError):
    """Raised when content generation fails"""

    def __init__(self, content_type: str, error_message: str):
        super().__init__(
            message=f"Failed to generate {content_type}: {error_message}",
            error_code="CONTENT_GENERATION_FAILED",
            details={"content_type": content_type, "error": error_message}
        )


# API Key Errors
class APIKeyError(APIException):
    """Base class for API key-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )


class InvalidAPIKeyError(APIKeyError):
    """Raised when API key is invalid"""

    def __init__(self):
        super().__init__(
            message="Invalid DashScope API key format",
            error_code="API_KEY_INVALID",
            details={"validation": "API key must start with 'sk-' and be at least 20 characters long"}
        )


class APIKeyNotConfiguredError(APIKeyError):
    """Raised when user hasn't configured an API key"""

    def __init__(self):
        super().__init__(
            message="API key not configured. Please configure your DashScope API key in user settings.",
            error_code="API_KEY_NOT_CONFIGURED",
            details={"action": "Configure API key in user profile"}
        )


class LLMAPIError(APIKeyError):
    """Raised when LLM API call fails"""

    def __init__(self, provider: str, error_message: str):
        super().__init__(
            message=f"{provider} API error: {error_message}",
            error_code="LLM_API_ERROR",
            details={"provider": provider, "error": error_message}
        )


# Validation Errors
class ValidationError(APIException):
    """Raised when request validation fails"""

    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            message=f"Validation error for field '{field}': {message}",
            details={"field": field, "message": message}
        )


class MissingRequiredFieldError(ValidationError):
    """Raised when required field is missing"""

    def __init__(self, field: str):
        super().__init__(
            field=field,
            message=f"Required field '{field}' is missing"
        )


class InvalidFieldValueError(ValidationError):
    """Raised when field value is invalid"""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            field=field,
            message=f"Invalid value for field '{field}': {reason}",
            details={"field": field, "value": value, "reason": reason}
        )


# Database Errors
class DatabaseError(APIException):
    """Base class for database-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            details=details
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails"""

    def __init__(self):
        super().__init__(
            message="Database connection failed",
            error_code="DB_CONNECTION_ERROR",
            details={"action": "Check database configuration"}
        )


class DatabaseOperationError(DatabaseError):
    """Raised when database operation fails"""

    def __init__(self, operation: str, error_message: str):
        super().__init__(
            message=f"Database operation '{operation}' failed: {error_message}",
            error_code="DB_OPERATION_ERROR",
            details={"operation": operation, "error": error_message}
        )


# System Errors
class SystemError(APIException):
    """Base class for system errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            details=details
        )


class RedisConnectionError(SystemError):
    """Raised when Redis connection fails"""

    def __init__(self):
        super().__init__(
            message="Redis connection failed",
            error_code="REDIS_CONNECTION_ERROR",
            details={"action": "Check Redis configuration"}
        )


class TaskQueueError(SystemError):
    """Raised when task queue operation fails"""

    def __init__(self, operation: str, error_message: str):
        super().__init__(
            message=f"Task queue operation '{operation}' failed: {error_message}",
            error_code="TASK_QUEUE_ERROR",
            details={"operation": operation, "error": error_message}
        )