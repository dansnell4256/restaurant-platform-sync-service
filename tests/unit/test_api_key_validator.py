"""Unit tests for API key validation."""

import pytest

from restaurant_sync_service.auth.api_key_validator import APIKeyValidator


@pytest.mark.unit
class TestAPIKeyValidator:
    """Test suite for APIKeyValidator."""

    def test_validator_initialization_with_single_key(self) -> None:
        """Test that validator initializes with a single API key."""
        validator = APIKeyValidator(api_keys=["test-key-123"])
        assert validator is not None

    def test_validator_initialization_with_multiple_keys(self) -> None:
        """Test that validator initializes with multiple API keys."""
        validator = APIKeyValidator(api_keys=["key1", "key2", "key3"])
        assert validator is not None

    def test_validator_initialization_with_empty_list_raises_error(self) -> None:
        """Test that initializing with empty key list raises ValueError."""
        with pytest.raises(ValueError, match="At least one API key must be provided"):
            APIKeyValidator(api_keys=[])

    def test_validate_returns_true_for_valid_key(self) -> None:
        """Test that validate returns True for a valid API key."""
        validator = APIKeyValidator(api_keys=["valid-key"])
        assert validator.validate("valid-key") is True

    def test_validate_returns_false_for_invalid_key(self) -> None:
        """Test that validate returns False for an invalid API key."""
        validator = APIKeyValidator(api_keys=["valid-key"])
        assert validator.validate("invalid-key") is False

    def test_validate_returns_false_for_empty_key(self) -> None:
        """Test that validate returns False for empty string."""
        validator = APIKeyValidator(api_keys=["valid-key"])
        assert validator.validate("") is False

    def test_validate_works_with_multiple_valid_keys(self) -> None:
        """Test that validate accepts any of multiple valid keys."""
        validator = APIKeyValidator(api_keys=["key1", "key2", "key3"])
        assert validator.validate("key1") is True
        assert validator.validate("key2") is True
        assert validator.validate("key3") is True
        assert validator.validate("invalid") is False

    def test_validate_is_case_sensitive(self) -> None:
        """Test that API key validation is case-sensitive."""
        validator = APIKeyValidator(api_keys=["TestKey123"])
        assert validator.validate("TestKey123") is True
        assert validator.validate("testkey123") is False
        assert validator.validate("TESTKEY123") is False

    def test_validate_handles_whitespace(self) -> None:
        """Test that validate does not strip whitespace."""
        validator = APIKeyValidator(api_keys=["key-with-no-spaces"])
        assert validator.validate(" key-with-no-spaces") is False
        assert validator.validate("key-with-no-spaces ") is False
        assert validator.validate(" key-with-no-spaces ") is False
