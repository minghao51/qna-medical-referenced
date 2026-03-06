"""API key authentication middleware.

This module provides authentication middleware that validates API keys
provided by clients via the X-API-Key header. When API keys are configured
in settings, all requests must include a valid key.

Authentication flow:
    1. Check if API keys are configured in settings
    2. If not configured, skip authentication (development mode)
    3. If configured, require X-API-Key header on all requests
    4. Validate the key against the configured set
    5. Reject with 401 if missing, 403 if invalid

Exempt paths:
    - / - Root path
    - /health - Health check endpoint
    - /docs - API documentation (Swagger UI)
    - /openapi.json - OpenAPI schema

Example:
    Configure API keys in .env:
        API_KEYS=key1,key2,key3

    Client request with authentication:
        curl -X POST http://localhost:8001/chat \\
          -H "X-API-Key: key1" \\
          -H "Content-Type: application/json" \\
          -d '{"message": "Hello"}'
"""

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings


class APIKeyConfig:
    """Configuration and caching for API keys.

    Caches API keys in memory to avoid repeated parsing of the
    comma-separated string from settings. Provides reload capability
    for dynamic key updates.

    Attributes:
        _keys: Cached set of valid API keys, or None if not loaded
    """

    _keys: set[str] | None = None

    @classmethod
    def get_keys(cls) -> set[str]:
        """Get the set of valid API keys.

        Loads from settings on first call, then caches the result.
        Empty set indicates authentication is disabled.

        Returns:
            Set of valid API key strings. Empty if none configured.
        """
        if cls._keys is None:
            keys_str = settings.api_keys or ""
            cls._keys = set(keys_str.split(",")) if keys_str else set()
        return cls._keys

    @classmethod
    def reload(cls):
        """Reload API keys from settings.

        Clears the cache so next get_keys() call will reload from
        settings. Useful for testing or dynamic configuration updates.
        """
        cls._keys = None


def get_api_keys() -> set[str]:
    """Get the configured API keys.

    Convenience function that delegates to APIKeyConfig.get_keys().

    Returns:
        Set of valid API key strings. Empty if authentication disabled.
    """
    return APIKeyConfig.get_keys()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for API key authentication.

    Validates X-API-Key header on all requests except exempt paths.
    Returns 401 if header missing, 403 if key invalid.

    Exempt paths:
        - / - Root
        - /health - Health check
        - /docs - Swagger UI documentation
        - /openapi.json - OpenAPI schema

    Example:
        Add to FastAPI app:
            from src.app.middleware.auth import APIKeyMiddleware
            app.add_middleware(APIKeyMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and validate API key.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler in chain

        Returns:
            Response from next handler

        Raises:
            HTTPException(401): If X-API-Key header is missing
            HTTPException(403): If API key is invalid
        """
        # Skip authentication for public endpoints
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get configured API keys
        api_keys = get_api_keys()

        # If no keys configured, authentication is disabled
        if not api_keys:
            return await call_next(request)

        # Validate API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")

        if api_key not in api_keys:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return await call_next(request)
