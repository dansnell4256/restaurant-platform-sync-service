"""Unit tests for PlatformAdapter base class."""

from decimal import Decimal

import pytest

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.models.menu_models import Category, MenuItem


class ConcretePlatformAdapter(PlatformAdapter):
    """Concrete implementation for testing the abstract base class."""

    def __init__(self, platform_name: str = "test_platform") -> None:
        """Initialize test adapter."""
        super().__init__(platform_name)

    def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
        """Test implementation that returns a simple dict."""
        return {"items": len(items), "categories": len(categories)}

    async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
        """Test implementation that always succeeds."""
        return True


@pytest.mark.unit
class TestPlatformAdapter:
    """Test suite for PlatformAdapter abstract base class."""

    def test_concrete_adapter_can_be_instantiated(self) -> None:
        """Test that concrete implementation can be instantiated."""
        adapter = ConcretePlatformAdapter("test_platform")
        assert adapter is not None
        assert adapter.platform_name == "test_platform"

    def test_format_menu_must_be_implemented(self) -> None:
        """Test that format_menu must be implemented by subclasses."""

        class IncompleteAdapter(PlatformAdapter):
            async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteAdapter("incomplete")  # type: ignore

    def test_publish_menu_must_be_implemented(self) -> None:
        """Test that publish_menu must be implemented by subclasses."""

        class IncompleteAdapter(PlatformAdapter):
            def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
                return {}

        with pytest.raises(TypeError):
            IncompleteAdapter("incomplete")  # type: ignore

    def test_format_menu_signature(self) -> None:
        """Test that format_menu has correct signature and return type."""
        adapter = ConcretePlatformAdapter()

        # Create test data
        items = [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Burger",
                price=Decimal("12.99"),
                category_id="cat_1",
            )
        ]
        categories = [Category(id="cat_1", restaurant_id="rest_123", name="Main Courses")]

        result = adapter.format_menu(items, categories)
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_publish_menu_signature(self) -> None:
        """Test that publish_menu has correct signature and return type."""
        adapter = ConcretePlatformAdapter()

        result = await adapter.publish_menu("rest_123", {"test": "data"})
        assert isinstance(result, bool)
        assert result is True

    def test_format_menu_can_return_none(self) -> None:
        """Test that format_menu can return None on failure."""

        class FailingAdapter(PlatformAdapter):
            def __init__(self) -> None:
                super().__init__("failing")

            def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
                return None

            async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
                return False

        adapter = FailingAdapter()
        items: list[MenuItem] = []
        categories: list[Category] = []

        result = adapter.format_menu(items, categories)
        assert result is None

    @pytest.mark.asyncio
    async def test_publish_menu_can_return_false(self) -> None:
        """Test that publish_menu can return False on failure."""

        class FailingAdapter(PlatformAdapter):
            def __init__(self) -> None:
                super().__init__("failing")

            def format_menu(self, items: list[MenuItem], categories: list[Category]) -> dict | None:
                return {}

            async def publish_menu(self, restaurant_id: str, formatted_menu: dict) -> bool:
                return False

        adapter = FailingAdapter()
        result = await adapter.publish_menu("rest_123", {})
        assert result is False
