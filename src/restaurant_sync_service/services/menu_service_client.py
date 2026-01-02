"""Client for interacting with the Menu Service API."""

import logging
from decimal import Decimal

import httpx

from restaurant_sync_service.models.menu_models import Category, MenuItem

logger = logging.getLogger(__name__)


class MenuServiceClient:
    """HTTP client for fetching menu data from the Menu Service.

    This client provides methods to fetch menu items and categories from
    the Menu Service REST API using service-to-service authentication.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        """Initialize the Menu Service client.

        Args:
            base_url: Base URL of the Menu Service API (e.g., "https://api.example.com")
            api_key: API key for service-to-service authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def get_menu_items(self, restaurant_id: str) -> list[MenuItem] | None:
        """Fetch menu items for a restaurant from the Menu Service.

        Args:
            restaurant_id: The restaurant ID to fetch items for

        Returns:
            List of MenuItem objects, empty list if no items exist, or None on failure
        """
        url = f"{self.base_url}/restaurants/{restaurant_id}/items"
        headers = {"X-API-Key": self.api_key}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                items = []
                for item_data in data.get("items", []):
                    # Convert price string to Decimal
                    item_data["price"] = Decimal(str(item_data["price"]))
                    items.append(MenuItem(**item_data))

                return items

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(f"Failed to fetch menu items for restaurant {restaurant_id}: {e}")  # pragma: no cover
            return None

    async def get_categories(self, restaurant_id: str) -> list[Category] | None:
        """Fetch categories for a restaurant from the Menu Service.

        Args:
            restaurant_id: The restaurant ID to fetch categories for

        Returns:
            List of Category objects, empty list if no categories exist, or None on failure
        """
        url = f"{self.base_url}/restaurants/{restaurant_id}/categories"
        headers = {"X-API-Key": self.api_key}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                categories = []
                for category_data in data.get("categories", []):
                    categories.append(Category(**category_data))

                return categories

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(f"Failed to fetch categories for restaurant {restaurant_id}: {e}")  # pragma: no cover
            return None

    async def get_menu_data(self, restaurant_id: str) -> tuple[list[MenuItem], list[Category]] | None:
        """Fetch complete menu data (items and categories) for a restaurant.

        This is a convenience method that fetches both menu items and categories
        in a single call. Both requests must succeed for data to be returned.

        Args:
            restaurant_id: The restaurant ID to fetch menu data for

        Returns:
            Tuple of (menu_items, categories), or None if either fetch fails
        """
        items = await self.get_menu_items(restaurant_id)
        if items is None:
            return None

        categories = await self.get_categories(restaurant_id)
        if categories is None:
            return None

        return (items, categories)
