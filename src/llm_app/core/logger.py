"""
Logging module for the LLM App.

This module provides centralized logging configuration and management.
"""

import datetime
import logging
from pathlib import Path
from typing import Optional

from ..config import Config


class LoggerManager:
    """Logging manager for centralized log handling."""

    _loggers: dict[str, logging.Logger] = {}

    def __init__(self, log_level: Optional[int] = None) -> None:
        """Initialize logger manager.

        Args:
            log_level: Logging level. Uses Config.LOG_LEVEL if None.
        """
        self.log_level = log_level or getattr(logging, Config.LOG_LEVEL.upper())
        self.log_dir = Path(__file__).parent.parent.parent / "logs"
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging settings."""
        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up logging format
        formatter = logging.Formatter(Config.LOG_FORMAT)

        # Get or create root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # Clear existing handlers
        root_logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler with daily rotation
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"llm_app_{current_date}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)

        return self._loggers[name]

    @classmethod
    def log_user_action(cls, uuid_value: str, action: str, details: str = "") -> None:
        """Log user actions for audit trail.

        Args:
            uuid_value: User UUID
            action: Action performed
            details: Additional details
        """
        logger = cls().get_logger("user_actions")
        logger.info(f"User: {uuid_value} | Action: {action} | Details: {details}")

    @classmethod
    def log_file_operation(cls, operation: str, file_info: str) -> None:
        """Log file operations.

        Args:
            operation: Operation type (upload, delete, etc.)
            file_info: File information
        """
        logger = cls().get_logger("file_operations")
        logger.info(f"File Operation: {operation} | Info: {file_info}")

    @classmethod
    def log_api_call(
        cls, endpoint: str, model: str, response_time: float, status: str
    ) -> None:
        """Log API calls for monitoring.

        Args:
            endpoint: API endpoint called
            model: Model used
            response_time: Time taken in seconds
            status: Success or error status
        """
        logger = cls().get_logger("api_calls")
        logger.info(
            f"API Call: {endpoint} | Model: {model} | "
            f"Response Time: {response_time:.2f}s | Status: {status}"
        )

    @classmethod
    def log_error(cls, error_type: str, error_message: str, context: str = "") -> None:
        """Log errors with context.

        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context
        """
        logger = cls().get_logger("errors")
        logger.error(
            f"Error Type: {error_type} | Message: {error_message} | Context: {context}"
        )

    @classmethod
    def log_task_execution(
        cls, task_type: str, task_id: str, status: str, duration: Optional[float] = None
    ) -> None:
        """Log task execution.

        Args:
            task_type: Type of task
            task_id: Task identifier
            status: Task status
            duration: Task duration in seconds
        """
        logger = cls().get_logger("tasks")
        duration_str = f" | Duration: {duration:.2f}s" if duration else ""
        logger.info(
            f"Task: {task_type} | ID: {task_id} | Status: {status}{duration_str}"
        )
