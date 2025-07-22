"""Authentication utilities for Whale Alert API."""
import hashlib
import secrets
from typing import Optional

from fastapi import HTTPException, status, Depends
from fastapi.security import APIKeyHeader

from api.config import api_settings


class APIKeyAuth:
    """Custom API Key authentication scheme."""
    
    def __init__(self, name: str = "X-API-Key"):
        # Use FastAPI's built-in APIKeyHeader for OpenAPI compatibility
        self.api_key_header = APIKeyHeader(name=name, auto_error=False)
        self.name = name

    async def __call__(self, api_key: Optional[str] = None) -> Optional[str]:
        """Extract and validate API key from request."""
        if not api_settings.REQUIRE_AUTH:
            return "disabled"
            
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "APIKey"},
            )
        
        if not self.is_valid_api_key(api_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )
        
        return api_key

    def is_valid_api_key(self, api_key: str) -> bool:
        """Validate API key using secure comparison."""
        valid_keys = [key.strip() for key in api_settings.API_KEYS.split(",")]
        
        # Use secure comparison to prevent timing attacks
        for valid_key in valid_keys:
            if valid_key and secrets.compare_digest(api_key, valid_key):
                return True
        
        return False


def generate_api_key(prefix: str = "wha", length: int = 32) -> str:
    """Generate a secure API key with optional prefix."""
    random_part = secrets.token_urlsafe(length)
    return f"{prefix}_{random_part}"


def hash_api_key(api_key: str) -> str:
    """Create a secure hash of an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


# Create the authentication instance
auth_instance = APIKeyAuth(name=api_settings.API_KEY_HEADER)

# Use FastAPI's APIKeyHeader directly for dependency injection
api_key_header = APIKeyHeader(name=api_settings.API_KEY_HEADER, auto_error=False)

# Authentication dependency function
async def api_key_auth(api_key: Optional[str] = Depends(api_key_header)) -> Optional[str]:
    """Authentication dependency for FastAPI routes."""
    return await auth_instance(api_key)