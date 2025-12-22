"""
Configuration module for the LLM App.

This module centralizes all configuration settings including database paths,
API settings, and application parameters.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Application configuration manager."""

    # Database configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./database.sqlite")

    # File storage configuration
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", "./uploads")

    # Redis configuration
    # Default to False - use memory-based queue by default
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes", "on")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_URL: str = os.getenv(
        "REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )

    # LLM API configuration
    DEFAULT_MODEL: str = "qwen-max"
    API_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Application settings
    TOKEN_EXPIRY_SECONDS: int = 24 * 60 * 60  # 24 hours
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: set[str] = {".txt", ".doc", ".docx", ".pdf"}

    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Streamlit configuration
    STREAMLIT_SERVER_PORT: int = 8501
    STREAMLIT_SERVER_ADDRESS: str = "0.0.0.0"
    STREAMLIT_SERVER_HEADLESS: bool = True

    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        Path(cls.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_database_dir(cls) -> Path:
        """Get database directory path."""
        return Path(cls.DATABASE_PATH).parent

    @classmethod
    def get_uploads_dir(cls) -> Path:
        """Get uploads directory path."""
        return Path(cls.UPLOADS_DIR)
