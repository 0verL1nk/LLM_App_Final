"""
Structured logging configuration for FastAPI backend
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict
from logging.handlers import RotatingFileHandler

from llm_app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application"""

    # Create logs directory
    logs_dir = Path(__file__).parent.parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))

    # File handler with rotation (max 10MB, keep 5 backups)
    log_file = logs_dir / "backend.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, settings.log_level.upper()))

    # Clear existing handlers and add new ones
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configure third-party loggers to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("rq").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


def log_request(
    logger: logging.Logger,
    request_data: Dict[str, Any],
    response_status: int,
    response_time: float
) -> None:
    """Log HTTP request with context"""
    logger.info(
        "HTTP Request",
        extra={
            "event_type": "http_request",
            "method": request_data.get("method"),
            "url": request_data.get("url"),
            "status_code": response_status,
            "response_time": response_time,
            "client_ip": request_data.get("client"),
        }
    )


def log_auth_event(
    logger: logging.Logger,
    event_type: str,
    username: str | None = None,
    success: bool = True,
    details: Dict[str, Any] | None = None
) -> None:
    """Log authentication-related events"""
    logger.info(
        f"Auth event: {event_type}",
        extra={
            "event_type": "auth_event",
            "auth_event_type": event_type,
            "username": username,
            "success": success,
            "details": details or {},
        }
    )


def log_task_event(
    logger: logging.Logger,
    task_id: str,
    task_type: str,
    status: str,
    user_id: str | None = None,
    details: Dict[str, Any] | None = None
) -> None:
    """Log task processing events"""
    logger.info(
        f"Task event: {task_type} - {status}",
        extra={
            "event_type": "task_event",
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "user_id": user_id,
            "details": details or {},
        }
    )


# Initialize logging on import
setup_logging()