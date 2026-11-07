"""Configuration management for RecallOps backend."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groq LLM Configuration
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")

    # Hindsight Memory Configuration
    hindsight_api_key: str = Field(..., alias="HINDSIGHT_API_KEY")
    hindsight_base_url: str = Field(default="https://api.hindsight.ai", alias="HINDSIGHT_BASE_URL")
    hindsight_bank_id: str = Field(..., alias="HINDSIGHT_BANK_ID")

    # Backend Configuration
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")

    # Frontend Configuration (for CORS)
    frontend_url: str = Field(default="http://localhost:8501", alias="FRONTEND_URL")

    # Optional SQLite for audit history
    database_url: str = Field(default="sqlite:///./recallops.db", alias="DATABASE_URL")

    # Application
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()