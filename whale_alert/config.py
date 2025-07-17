"""Configuration settings for the Whale Alert Telegram bot."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseSettings, PostgresDsn, validator

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

    # Application settings
    SESSION_NAME: str = "whale_alert"
    LOG_LEVEL: str = "INFO"

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("TIMESCALEDB_URL", pre=True)
    def ensure_timescaledb_scheme(cls, v: Optional[str]) -> str:
        """Ensure the database URL has the postgresql scheme."""
        if v is None:
            return ""
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
