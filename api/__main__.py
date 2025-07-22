"""Entry point for running the Whale Alert API via python -m api."""
import uvicorn

from api.config import api_settings


if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=api_settings.API_HOST,
        port=api_settings.API_PORT,
        log_level=api_settings.API_LOG_LEVEL,
    )
