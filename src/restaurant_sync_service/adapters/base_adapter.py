"""Base adapter for delivery platform integrations.

This module defines the abstract base class that all platform adapters must implement.
Following the pattern from the menu service, we use simple return values (None/False)
for expected failures rather than raising exceptions.
"""

from abc import ABC, abstractmethod
from typing import Any

from restaurant_sync_service.models.menu_models import Category, MenuItem


class PlatformAdapter(ABC):
    """Abstract base class for delivery platform adapters.

    All platform-specific adapters (DoorDash, Uber Eats, Grubhub, etc.) must
    inherit from this class and implement the abstract methods.

    The adapter follows a simple error handling pattern:
    - format_menu returns None on failure
    - publish_menu returns False on failure
    - The orchestration layer decides retry logic
    """

    def __init__(self, platform_name: str) -> None:
        """Initialize the platform adapter.

        Args:
            platform_name: Name of the delivery platform (e.g., 'doordash', 'ubereats')
        """
        self.platform_name = platform_name

    @abstractmethod
    def format_menu(
        self, items: list[MenuItem], categories: list[Category]
    ) -> dict[str, Any] | None:
        """Transform menu data to platform-specific format.

        This method takes internal menu representation and converts it to the
        format required by the specific delivery platform's API.

        Args:
            items: List of menu items to format
            categories: List of menu categories to format

        Returns:
            dict: Platform-specific formatted menu data, or None if formatting fails

        Note:
            Returns None on expected failures (e.g., validation errors, missing data).
            Let exceptions bubble up only for unexpected errors.
        """
        pass

    @abstractmethod
    async def publish_menu(self, restaurant_id: str, formatted_menu: dict[str, Any]) -> bool:
        """Publish formatted menu to the platform API.

        This method sends the formatted menu data to the delivery platform's API
        endpoint to update the restaurant's menu on their platform.

        Args:
            restaurant_id: Internal restaurant identifier
            formatted_menu: Menu data formatted for the platform (from format_menu)

        Returns:
            bool: True if publish succeeded, False otherwise

        Note:
            Returns False on expected failures (API errors, network issues).
            The service layer will handle retry logic.
        """
        pass
