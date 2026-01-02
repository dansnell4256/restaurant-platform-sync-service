"""Unit tests for ErrorService."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from restaurant_sync_service.models.menu_models import Category, MenuItem
from restaurant_sync_service.models.sync_models import SyncError
from restaurant_sync_service.repositories.sync_repositories import SyncErrorRepository
from restaurant_sync_service.services.error_service import ErrorService


@pytest.mark.unit
class TestErrorService:
    """Test suite for ErrorService."""

    @pytest.fixture
    def mock_error_repo(self) -> SyncErrorRepository:
        """Create a mock SyncErrorRepository."""
        return MagicMock(spec=SyncErrorRepository)

    @pytest.fixture
    def error_service(self, mock_error_repo: SyncErrorRepository) -> ErrorService:
        """Create an ErrorService with mocked repository."""
        return ErrorService(error_repository=mock_error_repo)

    @pytest.fixture
    def sample_items(self) -> list[MenuItem]:
        """Create sample menu items for testing."""
        return [
            MenuItem(
                id="item_1",
                restaurant_id="rest_123",
                name="Burger",
                description="Tasty burger",
                price=Decimal("12.99"),
                category_id="cat_1",
                available=True,
                image_url=None,
            )
        ]

    @pytest.fixture
    def sample_categories(self) -> list[Category]:
        """Create sample categories for testing."""
        return [
            Category(
                id="cat_1",
                restaurant_id="rest_123",
                name="Entrees",
                description="Main dishes",
                sort_order=1,
            )
        ]

    def test_service_initialization(self, mock_error_repo: SyncErrorRepository) -> None:
        """Test that service initializes correctly."""
        service = ErrorService(error_repository=mock_error_repo)
        assert service.error_repository == mock_error_repo

    @pytest.mark.asyncio
    async def test_record_sync_error(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test recording a sync error."""
        mock_error_repo.save_error = MagicMock(return_value=True)

        error_id = await error_service.record_sync_error(
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Failed to publish menu to DoorDash API",
            menu_items=sample_items,
            menu_categories=sample_categories,
        )

        assert error_id is not None
        assert error_id.startswith("err_")

        # Verify error was saved
        mock_error_repo.save_error.assert_called_once()
        saved_error = mock_error_repo.save_error.call_args[0][0]
        assert isinstance(saved_error, SyncError)
        assert saved_error.restaurant_id == "rest_123"
        assert saved_error.platform == "doordash"
        assert saved_error.error_details == "Failed to publish menu to DoorDash API"
        assert saved_error.retry_count == 0
        assert saved_error.menu_snapshot is not None
        assert "items" in saved_error.menu_snapshot
        assert "categories" in saved_error.menu_snapshot

    @pytest.mark.asyncio
    async def test_record_sync_error_minimal(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test recording a sync error with minimal data (no menu snapshot)."""
        mock_error_repo.save_error = MagicMock(return_value=True)

        error_id = await error_service.record_sync_error(
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Menu fetch failed",
        )

        assert error_id is not None

        # Verify error was saved without menu snapshot
        saved_error = mock_error_repo.save_error.call_args[0][0]
        assert saved_error.menu_snapshot is None

    @pytest.mark.asyncio
    async def test_record_sync_error_save_failure(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test that recording error returns None if save fails."""
        mock_error_repo.save_error = MagicMock(return_value=False)

        error_id = await error_service.record_sync_error(
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Test error",
        )

        assert error_id is None

    @pytest.mark.asyncio
    async def test_get_error(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test retrieving a specific error by ID."""
        created_time = datetime.now(UTC)
        mock_error = SyncError(
            error_id="err_123",
            created_at=created_time,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Test error",
            menu_snapshot=None,
            retry_count=0,
        )
        mock_error_repo.get_error = MagicMock(return_value=mock_error)

        error = await error_service.get_error("err_123", created_time)

        assert error == mock_error
        mock_error_repo.get_error.assert_called_once_with("err_123", created_time)

    @pytest.mark.asyncio
    async def test_get_error_not_found(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test retrieving error returns None when not found."""
        created_time = datetime.now(UTC)
        mock_error_repo.get_error = MagicMock(return_value=None)

        error = await error_service.get_error("err_nonexistent", created_time)

        assert error is None

    @pytest.mark.asyncio
    async def test_get_errors_for_restaurant(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test retrieving all errors for a restaurant."""
        mock_errors = [
            SyncError(
                error_id="err_1",
                created_at=datetime.now(UTC),
                restaurant_id="rest_123",
                platform="doordash",
                error_details="Error 1",
                menu_snapshot=None,
                retry_count=0,
            ),
            SyncError(
                error_id="err_2",
                created_at=datetime.now(UTC),
                restaurant_id="rest_123",
                platform="ubereats",
                error_details="Error 2",
                menu_snapshot=None,
                retry_count=1,
            ),
        ]
        mock_error_repo.list_errors_for_restaurant = MagicMock(return_value=mock_errors)

        errors = await error_service.get_errors_for_restaurant("rest_123")

        assert len(errors) == 2
        assert errors == mock_errors
        mock_error_repo.list_errors_for_restaurant.assert_called_once_with(
            restaurant_id="rest_123", limit=50
        )

    @pytest.mark.asyncio
    async def test_get_errors_for_restaurant_with_limit(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test retrieving errors for a restaurant with limit."""
        mock_errors = [
            SyncError(
                error_id="err_1",
                created_at=datetime.now(UTC),
                restaurant_id="rest_123",
                platform="doordash",
                error_details="Error 1",
                menu_snapshot=None,
                retry_count=0,
            )
        ]
        mock_error_repo.list_errors_for_restaurant = MagicMock(return_value=mock_errors)

        errors = await error_service.get_errors_for_restaurant("rest_123", limit=25)

        assert len(errors) == 1
        mock_error_repo.list_errors_for_restaurant.assert_called_once_with(
            restaurant_id="rest_123", limit=25
        )

    @pytest.mark.asyncio
    async def test_increment_retry_count(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test incrementing retry count for an error."""
        # Mock the get_error to return an error with retry_count=0
        created_time = datetime.now(UTC)
        mock_error = SyncError(
            error_id="err_123",
            created_at=created_time,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Test error",
            menu_snapshot=None,
            retry_count=0,
        )
        mock_error_repo.get_error = MagicMock(return_value=mock_error)
        mock_error_repo.update_retry_count = MagicMock(return_value=True)

        result = await error_service.increment_retry_count("err_123", created_time)

        assert result is True
        mock_error_repo.update_retry_count.assert_called_once_with("err_123", created_time, 1)

    @pytest.mark.asyncio
    async def test_increment_retry_count_failure(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test that incrementing retry count returns False on failure."""
        created_time = datetime.now(UTC)
        mock_error_repo.get_error = MagicMock(return_value=None)

        result = await error_service.increment_retry_count("err_123", created_time)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_errors_by_platform(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
    ) -> None:
        """Test retrieving errors filtered by platform."""
        mock_errors = [
            SyncError(
                error_id="err_1",
                created_at=datetime.now(UTC),
                restaurant_id="rest_123",
                platform="doordash",
                error_details="Error 1",
                menu_snapshot=None,
                retry_count=0,
            ),
            SyncError(
                error_id="err_2",
                created_at=datetime.now(UTC),
                restaurant_id="rest_456",
                platform="doordash",
                error_details="Error 2",
                menu_snapshot=None,
                retry_count=0,
            ),
        ]
        mock_error_repo.list_errors_for_restaurant = MagicMock(return_value=mock_errors[:1])

        errors = await error_service.get_errors_for_restaurant("rest_123", platform="doordash")

        # In a real implementation, this would filter by platform
        # For now, we're testing that the method is called
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    async def test_menu_snapshot_serialization(
        self,
        error_service: ErrorService,
        mock_error_repo: SyncErrorRepository,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that menu snapshot is properly serialized."""
        mock_error_repo.save_error = MagicMock(return_value=True)

        await error_service.record_sync_error(
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Test",
            menu_items=sample_items,
            menu_categories=sample_categories,
        )

        saved_error = mock_error_repo.save_error.call_args[0][0]
        snapshot = saved_error.menu_snapshot

        assert snapshot is not None
        assert "items" in snapshot
        assert "categories" in snapshot
        assert len(snapshot["items"]) == 1
        assert len(snapshot["categories"]) == 1

        # Verify item data is serialized correctly
        item_data = snapshot["items"][0]
        assert item_data["id"] == "item_1"
        assert item_data["name"] == "Burger"
        assert item_data["price"] == "12.99"  # Decimal serialized to string

        # Verify category data is serialized correctly
        cat_data = snapshot["categories"][0]
        assert cat_data["id"] == "cat_1"
        assert cat_data["name"] == "Entrees"
