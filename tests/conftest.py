"""Shared pytest fixtures and configuration for all tests."""

import pytest


@pytest.fixture
def mock_restaurant_id() -> str:
    """Fixture providing a standard test restaurant ID."""
    return "rest_123456"


@pytest.fixture
def mock_platform() -> str:
    """Fixture providing a standard test platform name."""
    return "doordash"


@pytest.fixture
def mock_menu_items() -> list[dict]:
    """Fixture providing sample menu items for testing."""
    return [
        {
            "id": "item_1",
            "name": "Cheeseburger",
            "description": "Classic beef cheeseburger",
            "price": 12.99,
            "category_id": "cat_1",
            "available": True,
        },
        {
            "id": "item_2",
            "name": "Caesar Salad",
            "description": "Fresh romaine with caesar dressing",
            "price": 9.99,
            "category_id": "cat_2",
            "available": True,
        },
    ]


@pytest.fixture
def mock_categories() -> list[dict]:
    """Fixture providing sample categories for testing."""
    return [
        {"id": "cat_1", "name": "Burgers", "sort_order": 1},
        {"id": "cat_2", "name": "Salads", "sort_order": 2},
    ]


@pytest.fixture
def mock_sync_status() -> dict:
    """Fixture providing a sample sync status record."""
    return {
        "restaurant_id": "rest_123456",
        "platform": "doordash",
        "status": "success",
        "last_sync_time": "2024-01-15T10:30:00Z",
        "item_count": 42,
        "external_menu_id": "ext_menu_789",
    }


@pytest.fixture
def mock_eventbridge_event() -> dict:
    """Fixture providing a sample EventBridge menu change event."""
    return {
        "version": "0",
        "id": "event_123",
        "detail-type": "MenuChanged",
        "source": "menu-service",
        "account": "123456789012",
        "time": "2024-01-15T10:30:00Z",
        "region": "us-east-1",
        "resources": [],
        "detail": {
            "restaurant_id": "rest_123456",
            "change_type": "menu_updated",
            "timestamp": "2024-01-15T10:30:00Z",
        },
    }
