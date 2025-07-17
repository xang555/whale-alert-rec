"""Configuration settings for the Whale Alert Telegram bot."""
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import PostgresDsn, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """Application settings."""

    # Telegram API credentials
    API_ID: int
    API_HASH: str
    PHONE_NUMBER: str
    CHANNEL_USERNAME: str = "whale_alert"

    # Database configuration
    TIMESCALEDB_URL: PostgresDsn

    # LLM Settings
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    LLM_MODEL: str = Field("gpt-4o", env="LLM_MODEL")
    LLM_TEMPERATURE: float = Field(0.0, env="LLM_TEMPERATURE")
    
    # Application settings
    SESSION_NAME: str = "whale_alert"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("TIMESCALEDB_URL", mode='before')
    @classmethod
    def ensure_timescaledb_scheme(cls, v: Any) -> str:
        """Ensure the database URL has the postgresql scheme."""
        if v is None:
            raise ValueError("TIMESCALEDB_URL is required")
            
        if isinstance(v, str):
            if not v.startswith(("postgresql://", "postgres://")):
                if "://" not in v:
                    v = f"postgresql://{v}"
                else:
                    raise ValueError("Database URL must start with 'postgresql://'")
        return v


# Create settings instance
settings = Settings()

# Configure logging
import logging

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
