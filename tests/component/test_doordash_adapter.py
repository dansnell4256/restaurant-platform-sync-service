"""Component tests for DoorDash platform adapter."""

from decimal import Decimal

import httpx
import pytest

from restaurant_sync_service.adapters.doordash_adapter import DoorDashAdapter
from restaurant_sync_service.models.menu_models import Category, MenuItem


@pytest.mark.component
class TestDoorDashAdapter:
    """Test suite for DoorDash adapter."""

    @pytest.fixture
    def adapter(self) -> DoorDashAdapter:
        """Create a DoorDash adapter instance for testing."""
        return DoorDashAdapter(
            client_id="test_client_id",
            client_secret="test_client_secret",
            environment="sandbox",
        )

    @pytest.fixture
    def sample_items(self) -> list[MenuItem]:
        """Sample menu items for testing."""
        return [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Cheeseburger",
                description="Classic beef cheeseburger with lettuce and tomato",
                price=Decimal("12.99"),
                category_id="cat_1",
                available=True,
                image_url="https://example.com/burger.jpg",
            ),
            MenuItem(
                id="item_2",
                restaurant_id="rest_123",
                name="Caesar Salad",
                description="Fresh romaine with caesar dressing",
                price=Decimal("9.99"),
                category_id="cat_2",
                available=True,
            ),
            MenuItem(
                id="item_3",
                restaurant_id="rest_123",
                name="Fries",
                description="Crispy french fries",
                price=Decimal("4.50"),
                category_id="cat_1",
                available=False,  # Not available
            ),
        ]

    @pytest.fixture
    def sample_categories(self) -> list[Category]:
        """Sample categories for testing."""
        return [
            Category(
                id="cat_1",
                restaurant_id="rest_123",
                name="Main Courses",
                description="Entrees and main dishes",
                sort_order=1,
            ),
            Category(
                id="cat_2",
                restaurant_id="rest_123",
                name="Salads",
                description="Fresh salads",
                sort_order=2,
            ),
        ]

    def test_adapter_initialization(self, adapter: DoorDashAdapter) -> None:
        """Test that adapter initializes with correct configuration."""
        assert adapter.platform_name == "doordash"
        assert adapter.client_id == "test_client_id"
        assert adapter.client_secret == "test_client_secret"
        assert adapter.environment == "sandbox"
        assert adapter.base_url == "https://openapi-sandbox.doordash.com"

    def test_adapter_production_url(self) -> None:
        """Test that production environment uses correct URL."""
        adapter = DoorDashAdapter(
            client_id="test",
            client_secret="test",
            environment="production",
        )
        assert adapter.base_url == "https://openapi.doordash.com"

    def test_format_menu_with_valid_data(
        self,
        adapter: DoorDashAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test formatting menu with valid items and categories."""
        result = adapter.format_menu(sample_items, sample_categories)

        assert result is not None
        assert "menu" in result
        assert "categories" in result["menu"]
        assert "items" in result["menu"]

        # Check categories
        categories = result["menu"]["categories"]
        assert len(categories) == 2
        assert categories[0]["name"] == "Main Courses"
        assert categories[0]["sort_order"] == 1

        # Check items (only available items should be included)
        items = result["menu"]["items"]
        assert len(items) == 2  # Only 2 available items

        burger = next(item for item in items if item["name"] == "Cheeseburger")
        assert burger["description"] == "Classic beef cheeseburger with lettuce and tomato"
        assert burger["price"] == 1299  # Price in cents
        assert burger["image_url"] == "https://example.com/burger.jpg"

    def test_format_menu_filters_unavailable_items(
        self,
        adapter: DoorDashAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that unavailable items are filtered out."""
        result = adapter.format_menu(sample_items, sample_categories)

        assert result is not None
        items = result["menu"]["items"]

        # Fries are marked as unavailable, should not be in output
        item_names = [item["name"] for item in items]
        assert "Fries" not in item_names
        assert "Cheeseburger" in item_names
        assert "Caesar Salad" in item_names

    def test_format_menu_with_empty_lists(self, adapter: DoorDashAdapter) -> None:
        """Test formatting with empty item and category lists."""
        result = adapter.format_menu([], [])

        assert result is not None
        assert result["menu"]["categories"] == []
        assert result["menu"]["items"] == []

    def test_format_menu_price_conversion(self, adapter: DoorDashAdapter) -> None:
        """Test that prices are correctly converted to cents."""
        items = [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Test Item",
                price=Decimal("19.99"),
                category_id="cat_1",
            )
        ]
        categories = [Category(id="cat_1", restaurant_id="rest_123", name="Test")]

        result = adapter.format_menu(items, categories)

        assert result is not None
        assert result["menu"]["items"][0]["price"] == 1999

    @pytest.mark.asyncio
    async def test_publish_menu_success(self, adapter: DoorDashAdapter, httpx_mock) -> None:
        """Test successful menu publication to DoorDash API."""
        # Mock the auth token request
        httpx_mock.add_response(
            url="https://openapi-sandbox.doordash.com/auth/token",
            method="POST",
            json={"access_token": "test_token_123", "expires_in": 3600},
            status_code=200,
        )

        # Mock the menu update request
        httpx_mock.add_response(
            url="https://openapi-sandbox.doordash.com/v1/stores/ext_rest_123/menu",
            method="PUT",
            json={"status": "success"},
            status_code=200,
        )

        formatted_menu = {"menu": {"categories": [], "items": []}}
        result = await adapter.publish_menu("rest_123", formatted_menu)

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_menu_auth_failure(self, adapter: DoorDashAdapter, httpx_mock) -> None:
        """Test menu publication when authentication fails."""
        # Mock failed auth request
        httpx_mock.add_response(
            url="https://openapi-sandbox.doordash.com/auth/token",
            method="POST",
            status_code=401,
        )

        formatted_menu = {"menu": {"categories": [], "items": []}}
        result = await adapter.publish_menu("rest_123", formatted_menu)

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_menu_api_failure(self, adapter: DoorDashAdapter, httpx_mock) -> None:
        """Test menu publication when API request fails."""
        # Mock successful auth
        httpx_mock.add_response(
            url="https://openapi-sandbox.doordash.com/auth/token",
            method="POST",
            json={"access_token": "test_token_123", "expires_in": 3600},
            status_code=200,
        )

        # Mock failed menu update
        httpx_mock.add_response(
            url="https://openapi-sandbox.doordash.com/v1/stores/ext_rest_123/menu",
            method="PUT",
            status_code=500,
        )

        formatted_menu = {"menu": {"categories": [], "items": []}}
        result = await adapter.publish_menu("rest_123", formatted_menu)

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_menu_network_error(self, adapter: DoorDashAdapter, httpx_mock) -> None:
        """Test menu publication when network error occurs."""
        # Mock network error
        httpx_mock.add_exception(
            httpx.ConnectError("Connection failed"),
            url="https://openapi-sandbox.doordash.com/auth/token",
        )

        formatted_menu = {"menu": {"categories": [], "items": []}}
        result = await adapter.publish_menu("rest_123", formatted_menu)

        assert result is False
