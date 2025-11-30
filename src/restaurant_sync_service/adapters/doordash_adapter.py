"""DoorDash platform adapter implementation.

This adapter transforms menu data to DoorDash's API format and publishes
updates to their platform via the DoorDash Drive API.
"""

import logging
from typing import Any

import httpx

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.models.menu_models import Category, MenuItem

logger = logging.getLogger(__name__)


class DoorDashAdapter(PlatformAdapter):
    """Adapter for DoorDash Drive API integration.

    Handles menu formatting and publication to DoorDash's platform.
    Uses OAuth 2.0 client credentials flow for authentication.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        environment: str = "sandbox",
    ) -> None:
        """Initialize DoorDash adapter.

        Args:
            client_id: DoorDash API client ID
            client_secret: DoorDash API client secret
            environment: API environment ('sandbox' or 'production')
        """
        super().__init__("doordash")
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment

        # Set base URL based on environment
        if environment == "production":
            self.base_url = "https://openapi.doordash.com"
        else:
            self.base_url = "https://openapi-sandbox.doordash.com"

    def format_menu(
        self, items: list[MenuItem], categories: list[Category]
    ) -> dict[str, Any] | None:
        """Transform menu data to DoorDash format.

        DoorDash expects:
        - Categories with names and sort order
        - Items with prices in cents (not dollars)
        - Only available items

        Args:
            items: List of menu items to format
            categories: List of menu categories to format

        Returns:
            dict: DoorDash-formatted menu data, or None if formatting fails
        """
        try:
            # Filter only available items
            available_items = [item for item in items if item.available]

            # Format categories
            formatted_categories = [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description,
                    "sort_order": cat.sort_order,
                }
                for cat in categories
            ]

            # Format items - convert prices to cents
            formatted_items = [
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": int(item.price * 100),  # Convert to cents
                    "category_id": item.category_id,
                    "image_url": item.image_url,
                }
                for item in available_items
            ]

            return {
                "menu": {
                    "categories": formatted_categories,
                    "items": formatted_items,
                }
            }

        except Exception as e:
            logger.error(f"Failed to format menu for DoorDash: {e}")
            return None

    async def publish_menu(self, restaurant_id: str, formatted_menu: dict[str, Any]) -> bool:
        """Publish formatted menu to DoorDash API.

        Authenticates using OAuth 2.0 client credentials flow, then
        sends a PUT request to update the restaurant's menu.

        Args:
            restaurant_id: Internal restaurant identifier
            formatted_menu: Menu data formatted for DoorDash (from format_menu)

        Returns:
            bool: True if publish succeeded, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Get access token
                auth_response = await client.post(
                    f"{self.base_url}/auth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )

                if auth_response.status_code != 200:
                    logger.error(f"DoorDash auth failed: {auth_response.status_code}")
                    return False

                access_token = auth_response.json()["access_token"]

                # Step 2: Update menu
                # Use restaurant_id with 'ext_' prefix as external store ID
                store_id = f"ext_{restaurant_id}"
                menu_response = await client.put(
                    f"{self.base_url}/v1/stores/{store_id}/menu",
                    json=formatted_menu,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if menu_response.status_code == 200:
                    logger.info(f"Successfully published menu to DoorDash for {restaurant_id}")
                    return True
                else:
                    logger.error(f"DoorDash menu update failed: {menu_response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"DoorDash publish_menu failed: {e}")
            return False
