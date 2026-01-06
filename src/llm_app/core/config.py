"""
Configuration management for FastAPI backend
"""
import warnings
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Configuration
    project_name: str = Field(default="Literature Reading Assistant", description="Project name")
    api_v1_str: str = Field(default="/api/v1", description="API version prefix")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Security
    # Default provided to prevent crash on startup, but warns if used
    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_SECRET_KEY_12345", 
        description="Secret key for JWT tokens"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=1440, description="Token expiration in minutes (24h)")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./database.sqlite",
        description="Database connection URL"
    )

    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: str | None = Field(default=None, description="Redis password")

    # DashScope API (optional - per-user configuration)
    dashscope_api_key: str | None = Field(default=None, description="Default DashScope API key (optional)")

    # File Upload
    max_file_size: int = Field(default=52428800, description="Max file size in bytes (50MB)")
    allowed_file_extensions: str = Field(
        default="pdf,docx,txt",
        description="Comma-separated list of allowed file extensions"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="API rate limit per minute")

    # Task Queue
    rq_default_timeout: int = Field(default=300, description="Default RQ task timeout in seconds")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    settings = Settings()
    if settings.secret_key == "CHANGE_ME_IN_PRODUCTION_SECRET_KEY_12345":
        print("\n" + "="*80)
        print("WARNING: You are using the default insecure SECRET_KEY.")
        print("Please set 'SECRET_KEY' in your .env file for production use.")
        print("="*80 + "\n")
    return settings


# Global settings instance
settings = get_settings()
