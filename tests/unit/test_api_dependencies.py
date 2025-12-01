"""Unit tests for FastAPI authentication dependencies."""

import pytest
from fastapi import HTTPException

from restaurant_sync_service.auth.api_dependencies import get_api_key_from_header
from restaurant_sync_service.auth.api_key_validator import APIKeyValidator


@pytest.mark.unit
class TestGetAPIKeyFromHeader:
    """Test suite for get_api_key_from_header dependency."""

    def test_returns_api_key_when_valid(self) -> None:
        """Test that dependency returns API key when valid."""
        validator = APIKeyValidator(api_keys=["valid-key"])
        api_key = get_api_key_from_header(x_api_key="valid-key", validator=validator)
        assert api_key == "valid-key"

    def test_raises_401_when_api_key_invalid(self) -> None:
        """Test that dependency raises 401 for invalid API key."""
        validator = APIKeyValidator(api_keys=["valid-key"])

        with pytest.raises(HTTPException) as exc_info:
            get_api_key_from_header(x_api_key="invalid-key", validator=validator)

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    def test_raises_401_when_api_key_missing(self) -> None:
        """Test that dependency raises 401 when API key header is missing."""
        validator = APIKeyValidator(api_keys=["valid-key"])

        with pytest.raises(HTTPException) as exc_info:
            get_api_key_from_header(x_api_key=None, validator=validator)

        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail

    def test_raises_401_when_api_key_empty(self) -> None:
        """Test that dependency raises 401 for empty API key."""
        validator = APIKeyValidator(api_keys=["valid-key"])

        with pytest.raises(HTTPException) as exc_info:
            get_api_key_from_header(x_api_key="", validator=validator)

        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail
