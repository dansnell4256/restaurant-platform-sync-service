"""Unit tests for DoorDash adapter."""

from decimal import Decimal

import pytest

from restaurant_sync_service.adapters.doordash_adapter import DoorDashAdapter
from restaurant_sync_service.models.menu_models import Category, MenuItem


@pytest.mark.unit
class TestDoorDashAdapter:
    """Test suite for DoorDashAdapter."""

    @pytest.fixture
    def adapter(self) -> DoorDashAdapter:
        """Create a DoorDash adapter for testing."""
        return DoorDashAdapter(
            client_id="test_client_id",
            client_secret="test_client_secret",
            environment="sandbox",
        )

    @pytest.fixture
    def sample_items(self) -> list[MenuItem]:
        """Create sample menu items for testing."""
        return [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Cheeseburger",
                description="Delicious burger",
                price=Decimal("12.99"),
                category_id="cat_1",
                available=True,
                image_url="https://example.com/burger.jpg",
            ),
            MenuItem(
                id="item_2",
                restaurant_id="rest_123",
                name="Fries",
                description="Crispy fries",
                price=Decimal("4.50"),
                category_id="cat_1",
                available=True,
            ),
            MenuItem(
                id="item_3",
                restaurant_id="rest_123",
                name="Out of Stock Item",
                description="Not available",
                price=Decimal("8.00"),
                category_id="cat_1",
                available=False,
            ),
        ]

    @pytest.fixture
    def sample_categories(self) -> list[Category]:
        """Create sample categories for testing."""
        return [
            Category(
                id="cat_1",
                restaurant_id="rest_123",
                name="Main Dishes",
                description="Our main menu items",
                sort_order=1,
            ),
            Category(
                id="cat_2",
                restaurant_id="rest_123",
                name="Sides",
                description="Side dishes",
                sort_order=2,
            ),
        ]

    def test_adapter_initialization_sandbox(self) -> None:
        """Test adapter initializes with sandbox environment."""
        adapter = DoorDashAdapter(
            client_id="test_id",
            client_secret="test_secret",
            environment="sandbox",
        )

        assert adapter.client_id == "test_id"
        assert adapter.client_secret == "test_secret"
        assert adapter.environment == "sandbox"
        assert adapter.base_url == "https://openapi-sandbox.doordash.com"
        assert adapter.platform_name == "doordash"

    def test_adapter_initialization_production(self) -> None:
        """Test adapter initializes with production environment."""
        adapter = DoorDashAdapter(
            client_id="test_id",
            client_secret="test_secret",
            environment="production",
        )

        assert adapter.base_url == "https://openapi.doordash.com"

    def test_format_menu_success(
        self,
        adapter: DoorDashAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test successful menu formatting."""
        result = adapter.format_menu(sample_items, sample_categories)

        assert result is not None
        assert "menu" in result
        assert "categories" in result["menu"]
        assert "items" in result["menu"]

        # Check categories
        assert len(result["menu"]["categories"]) == 2
        cat = result["menu"]["categories"][0]
        assert cat["id"] == "cat_1"
        assert cat["name"] == "Main Dishes"
        assert cat["description"] == "Our main menu items"
        assert cat["sort_order"] == 1

        # Check items - should only include available items
        assert len(result["menu"]["items"]) == 2  # Only 2 available items

        # Check first item
        item = result["menu"]["items"][0]
        assert item["id"] == "item_1"
        assert item["name"] == "Cheeseburger"
        assert item["description"] == "Delicious burger"
        assert item["price"] == 1299  # $12.99 converted to cents
        assert item["category_id"] == "cat_1"
        assert item["image_url"] == "https://example.com/burger.jpg"

        # Check second item
        item2 = result["menu"]["items"][1]
        assert item2["id"] == "item_2"
        assert item2["price"] == 450  # $4.50 converted to cents

    def test_format_menu_filters_unavailable_items(
        self,
        adapter: DoorDashAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that format_menu excludes unavailable items."""
        result = adapter.format_menu(sample_items, sample_categories)

        assert result is not None
        item_ids = [item["id"] for item in result["menu"]["items"]]
        assert "item_1" in item_ids
        assert "item_2" in item_ids
        assert "item_3" not in item_ids  # Should be filtered out

    def test_format_menu_converts_prices_to_cents(
        self,
        adapter: DoorDashAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that prices are correctly converted from dollars to cents."""
        result = adapter.format_menu(sample_items, sample_categories)

        assert result is not None
        items = result["menu"]["items"]

        # $12.99 -> 1299 cents
        assert items[0]["price"] == 1299
        # $4.50 -> 450 cents
        assert items[1]["price"] == 450

    def test_format_menu_with_empty_lists(
        self,
        adapter: DoorDashAdapter,
    ) -> None:
        """Test formatting with empty item and category lists."""
        result = adapter.format_menu([], [])

        assert result is not None
        assert result["menu"]["categories"] == []
        assert result["menu"]["items"] == []

    def test_format_menu_with_no_available_items(
        self,
        adapter: DoorDashAdapter,
        sample_categories: list[Category],
    ) -> None:
        """Test formatting when all items are unavailable."""
        unavailable_items = [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Out of Stock",
                description="Not available",
                price=Decimal("10.00"),
                category_id="cat_1",
                available=False,
            ),
        ]

        result = adapter.format_menu(unavailable_items, sample_categories)

        assert result is not None
        assert len(result["menu"]["items"]) == 0
        assert len(result["menu"]["categories"]) == 2  # Categories still present

    def test_format_menu_handles_item_without_image_url(
        self,
        adapter: DoorDashAdapter,
        sample_categories: list[Category],
    ) -> None:
        """Test formatting items that don't have an image URL."""
        items = [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="No Image Item",
                description="Item without image",
                price=Decimal("5.00"),
                category_id="cat_1",
                available=True,
                image_url=None,
            ),
        ]

        result = adapter.format_menu(items, sample_categories)

        assert result is not None
        assert len(result["menu"]["items"]) == 1
        assert result["menu"]["items"][0]["image_url"] is None

    def test_format_menu_handles_exception(
        self,
        adapter: DoorDashAdapter,
    ) -> None:
        """Test that format_menu returns None when an exception occurs."""
        # Pass invalid data that will cause an exception
        # (e.g., object without expected attributes)
        invalid_items = [{"invalid": "data"}]  # type: ignore
        invalid_categories = [{"invalid": "data"}]  # type: ignore

        result = adapter.format_menu(invalid_items, invalid_categories)  # type: ignore

        assert result is None
