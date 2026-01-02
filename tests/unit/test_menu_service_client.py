"""Unit tests for MenuServiceClient."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from restaurant_sync_service.models.menu_models import Category, MenuItem
from restaurant_sync_service.services.menu_service_client import MenuServiceClient


@pytest.mark.unit
class TestMenuServiceClient:
    """Test suite for MenuServiceClient."""

    @pytest.fixture
    def client(self) -> MenuServiceClient:
        """Create a MenuServiceClient with test configuration."""
        return MenuServiceClient(
            base_url="https://api.test.com",
            api_key="test-api-key",
        )

    @pytest.mark.asyncio
    async def test_client_initialization(self) -> None:
        """Test that client initializes with correct configuration."""
        client = MenuServiceClient(base_url="https://api.test.com", api_key="test-key")
        assert client.base_url == "https://api.test.com"
        assert client.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_get_menu_items_success(self, client: MenuServiceClient) -> None:
        """Test successfully fetching menu items from menu service."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "item_1",
                    "restaurant_id": "rest_123",
                    "name": "Burger",
                    "description": "Tasty burger",
                    "price": "12.99",
                    "category_id": "cat_1",
                    "available": True,
                    "image_url": None,
                },
                {
                    "id": "item_2",
                    "restaurant_id": "rest_123",
                    "name": "Salad",
                    "description": "Fresh salad",
                    "price": "9.99",
                    "category_id": "cat_2",
                    "available": True,
                    "image_url": "https://example.com/salad.jpg",
                },
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            items = await client.get_menu_items("rest_123")

        assert len(items) == 2
        assert isinstance(items[0], MenuItem)
        assert items[0].id == "item_1"
        assert items[0].name == "Burger"
        assert items[0].price == Decimal("12.99")
        assert items[1].id == "item_2"
        assert items[1].image_url == "https://example.com/salad.jpg"

    @pytest.mark.asyncio
    async def test_get_menu_items_empty_list(self, client: MenuServiceClient) -> None:
        """Test fetching menu items returns empty list when no items exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            items = await client.get_menu_items("rest_123")

        assert items == []

    @pytest.mark.asyncio
    async def test_get_menu_items_api_error(self, client: MenuServiceClient) -> None:
        """Test that API errors return None."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            items = await client.get_menu_items("rest_123")

        assert items is None

    @pytest.mark.asyncio
    async def test_get_menu_items_network_error(self, client: MenuServiceClient) -> None:
        """Test that network errors return None."""
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("Connection failed", request=MagicMock()),
        ):
            items = await client.get_menu_items("rest_123")

        assert items is None

    @pytest.mark.asyncio
    async def test_get_menu_items_includes_auth_header(self, client: MenuServiceClient) -> None:
        """Test that API key is included in request headers."""
        mock_get = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        with patch("httpx.AsyncClient.get", mock_get):
            await client.get_menu_items("rest_123")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["X-API-Key"] == "test-api-key"

    @pytest.mark.asyncio
    async def test_get_categories_success(self, client: MenuServiceClient) -> None:
        """Test successfully fetching categories from menu service."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "categories": [
                {
                    "id": "cat_1",
                    "restaurant_id": "rest_123",
                    "name": "Entrees",
                    "description": "Main dishes",
                    "sort_order": 1,
                },
                {
                    "id": "cat_2",
                    "restaurant_id": "rest_123",
                    "name": "Sides",
                    "description": None,
                    "sort_order": 2,
                },
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            categories = await client.get_categories("rest_123")

        assert len(categories) == 2
        assert isinstance(categories[0], Category)
        assert categories[0].id == "cat_1"
        assert categories[0].name == "Entrees"
        assert categories[0].sort_order == 1
        assert categories[1].description is None

    @pytest.mark.asyncio
    async def test_get_categories_empty_list(self, client: MenuServiceClient) -> None:
        """Test fetching categories returns empty list when none exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"categories": []}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            categories = await client.get_categories("rest_123")

        assert categories == []

    @pytest.mark.asyncio
    async def test_get_categories_api_error(self, client: MenuServiceClient) -> None:
        """Test that API errors return None for categories."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            categories = await client.get_categories("rest_123")

        assert categories is None

    @pytest.mark.asyncio
    async def test_get_categories_network_error(self, client: MenuServiceClient) -> None:
        """Test that network errors return None for categories."""
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("Timeout", request=MagicMock()),
        ):
            categories = await client.get_categories("rest_123")

        assert categories is None

    @pytest.mark.asyncio
    async def test_get_menu_data_success(self, client: MenuServiceClient) -> None:
        """Test successfully fetching complete menu data (items and categories)."""
        mock_items_response = MagicMock()
        mock_items_response.status_code = 200
        mock_items_response.json.return_value = {
            "items": [
                {
                    "id": "item_1",
                    "restaurant_id": "rest_123",
                    "name": "Burger",
                    "description": "Tasty burger",
                    "price": "12.99",
                    "category_id": "cat_1",
                    "available": True,
                    "image_url": None,
                }
            ]
        }

        mock_categories_response = MagicMock()
        mock_categories_response.status_code = 200
        mock_categories_response.json.return_value = {
            "categories": [
                {
                    "id": "cat_1",
                    "restaurant_id": "rest_123",
                    "name": "Entrees",
                    "description": "Main dishes",
                    "sort_order": 1,
                }
            ]
        }

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[mock_items_response, mock_categories_response],
        ):
            menu_data = await client.get_menu_data("rest_123")

        assert menu_data is not None
        items, categories = menu_data
        assert len(items) == 1
        assert len(categories) == 1
        assert items[0].name == "Burger"
        assert categories[0].name == "Entrees"

    @pytest.mark.asyncio
    async def test_get_menu_data_items_failure(self, client: MenuServiceClient) -> None:
        """Test that get_menu_data returns None if items fetch fails."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.RequestError("Error", request=MagicMock())):
            menu_data = await client.get_menu_data("rest_123")

        assert menu_data is None

    @pytest.mark.asyncio
    async def test_get_menu_data_categories_failure(self, client: MenuServiceClient) -> None:
        """Test that get_menu_data returns None if categories fetch fails."""
        mock_items_response = MagicMock()
        mock_items_response.status_code = 200
        mock_items_response.json.return_value = {"items": []}

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[mock_items_response, httpx.RequestError("Error", request=MagicMock())],
        ):
            menu_data = await client.get_menu_data("rest_123")

        assert menu_data is None
