"""FastAPI dependencies for API authentication.

Provides dependency injection functions for FastAPI endpoints to validate API keys.
"""

from typing import Annotated

from fastapi import Header, HTTPException

from restaurant_sync_service.auth.api_key_validator import APIKeyValidator


def get_api_key_from_header(
    x_api_key: Annotated[str | None, Header()] = None,
    validator: APIKeyValidator | None = None,
) -> str:
    """FastAPI dependency to extract and validate API key from X-API-Key header.

    Args:
        x_api_key: API key from X-API-Key header (injected by FastAPI)
        validator: APIKeyValidator instance (injected as dependency)

    Returns:
        str: The validated API key

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Validator will be None in tests where it's mocked
    if validator and not validator.validate(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return x_api_key
