"""Configuration for Whale Alert API."""
from pathlib import Path

from dotenv import load_dotenv
from pydantic import PostgresDsn, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file if present
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class APISettings(BaseSettings):
    """Configuration settings for Whale Alert API."""

    # Database connection to Materialize (PostgreSQL wire protocol)
    TIMESCALEDB_URL: PostgresDsn

    # Server settings
    API_HOST: str = Field("0.0.0.0", env="API_HOST")
    API_PORT: int = Field(8000, env="API_PORT")
    API_LOG_LEVEL: str = Field("info", env="API_LOG_LEVEL")

    # Authentication settings
    API_KEYS: str = Field("test_key_123", env="API_KEYS", description="Comma-separated list of valid API keys")
    API_KEY_HEADER: str = Field("X-API-Key", env="API_KEY_HEADER", description="Header name for API key")
    REQUIRE_AUTH: bool = Field(True, env="REQUIRE_AUTH", description="Whether to require authentication")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


api_settings = APISettings()
