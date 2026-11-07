"""Configuration management for RecallOps backend."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groq LLM Configuration
    groq_api_key: str = Field(default="test_groq_key", alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")

    # Hindsight Memory Configuration
    hindsight_api_key: str = Field(default="test_hindsight_key", alias="HINDSIGHT_API_KEY")
    hindsight_base_url: str = Field(default="https://api.hindsight.ai", alias="HINDSIGHT_BASE_URL")
    hindsight_bank_id: str = Field(default="test_bank", alias="HINDSIGHT_BANK_ID")

    # Backend Configuration
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")

    # Frontend Configuration (for CORS)
    frontend_url: str = Field(default="http://localhost:8501", alias="FRONTEND_URL")

    # PostgreSQL for audit history (REQUIRED - no SQLite fallback)
    database_url: str = Field(default="postgresql://recallops:password@localhost:5432/recallops", alias="DATABASE_URL")

    # Application
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Mock Mode - EXPLICITLY configurable, never silent
    mock_mode: bool = Field(default=False, alias="MOCK_MODE")

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False,
        extra = "ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
