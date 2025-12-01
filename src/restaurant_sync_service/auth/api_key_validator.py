"""API key validation for admin endpoints.

This module provides API key validation following the same pattern as the menu service.
API keys are validated using simple string matching against a configured set of valid keys.
"""


class APIKeyValidator:
    """Validates API keys for admin endpoint authentication.

    Following the menu service pattern, this uses dependency injection
    for configuration and simple return values for validation results.
    """

    def __init__(self, api_keys: list[str]) -> None:
        """Initialize validator with list of valid API keys.

        Args:
            api_keys: List of valid API key strings

        Raises:
            ValueError: If api_keys list is empty
        """
        if not api_keys:
            raise ValueError("At least one API key must be provided")

        self.api_keys = set(api_keys)  # Use set for O(1) lookup

    def validate(self, api_key: str) -> bool:
        """Validate an API key.

        Args:
            api_key: The API key to validate

        Returns:
            bool: True if valid, False otherwise
        """
        return api_key in self.api_keys
