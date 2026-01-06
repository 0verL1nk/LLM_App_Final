"""
Global exception handlers for FastAPI application
"""
from typing import Any, Dict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from llm_app.core.exceptions import APIException, ErrorResponse
from llm_app.core.logger import get_logger

logger = get_logger(__name__)


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Global exception handler for custom APIException

    Args:
        request: FastAPI request object
        exc: APIException instance

    Returns:
        JSONResponse: Standardized error response
    """
    # Log the error
    logger.error(
        f"API Exception: {exc.error_code} - {exc.detail['message']}",
        extra={
            "request_url": str(request.url),
            "request_method": request.method,
            "error_code": exc.error_code,
            "error_details": exc.detail.get('details')
        }
    )

    # Return standardized error response
    error_response = ErrorResponse(
        error=exc.error_code,
        message=exc.detail["message"],
        details=exc.detail.get("details")
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Global exception handler for Pydantic validation errors

    Args:
        request: FastAPI request object
        exc: RequestValidationError instance

    Returns:
        JSONResponse: Standardized validation error response
    """
    # Log the error
    logger.warning(
        f"Validation Error: {len(exc.errors())} validation error(s)",
        extra={
            "request_url": str(request.url),
            "request_method": request.method,
            "validation_errors": exc.errors()
        }
    )

    # Format validation errors for client
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": ".".join(str(x) for x in error.get("loc", [])),
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "validation_error")
        })

    error_response = ErrorResponse(
        error="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": error_details}
    )

    return JSONResponse(
        status_code=422,
        content=error_response.dict()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled exceptions

    Args:
        request: FastAPI request object
        exc: Unhandled exception

    Returns:
        JSONResponse: Standardized error response
    """
    # Log the error with full traceback
    logger.error(
        f"Unhandled Exception: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_url": str(request.url),
            "request_method": request.method,
            "exception_type": type(exc).__name__,
        },
        exc_info=True
    )

    # Return generic error message (don't expose internal details)
    error_response = ErrorResponse(
        error="INTERNAL_SERVER_ERROR",
        message="An internal server error occurred",
        details={
            "type": type(exc).__name__
            # Note: Not including str(exc) to avoid exposing sensitive information
        }
    )

    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for standard HTTPException

    Args:
        request: FastAPI request object
        exc: HTTPException instance

    Returns:
        JSONResponse: Standardized error response
    """
    # Log the error
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "request_url": str(request.url),
            "request_method": request.method,
            "status_code": exc.status_code
        }
    )

    # Check if detail is already a dict (from our APIException)
    if isinstance(exc.detail, dict):
        error_response = ErrorResponse(
            error=exc.detail.get("error", "HTTP_ERROR"),
            message=exc.detail.get("message", "HTTP error occurred"),
            details=exc.detail.get("details")
        )
    else:
        error_response = ErrorResponse(
            error="HTTP_ERROR",
            message=str(exc.detail),
            details=None
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


def setup_exception_handlers(app) -> None:
    """
    Register all global exception handlers with the FastAPI app

    Args:
        app: FastAPI application instance
    """
    # Register custom exception handlers
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Global exception handlers registered successfully")


# Additional utility functions for error handling


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Utility function to create a standardized error response dictionary

    Args:
        status_code: HTTP status code
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Additional error details (optional)

    Returns:
        Dict: Standardized error response
    """
    return {
        "error": error_code,
        "message": message,
        "details": details
    }


def create_success_response(
    message: str,
    data: Any = None,
    meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Utility function to create a standardized success response

    Args:
        message: Success message
        data: Response data (optional)
        meta: Additional metadata (optional)

    Returns:
        Dict: Standardized success response
    """
    response = {
        "success": True,
        "message": message
    }

    if data is not None:
        response["data"] = data

    if meta is not None:
        response["meta"] = meta

    return response