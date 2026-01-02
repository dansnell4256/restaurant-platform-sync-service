"""Unit tests for SyncService."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.models.menu_models import Category, MenuItem
from restaurant_sync_service.models.sync_models import SyncStatus, SyncStatusEnum
from restaurant_sync_service.repositories.sync_repositories import (
    SyncStatusRepository,
)
from restaurant_sync_service.services.menu_service_client import MenuServiceClient
from restaurant_sync_service.services.sync_service import SyncService


@pytest.mark.unit
class TestSyncService:
    """Test suite for SyncService."""

    @pytest.fixture
    def mock_menu_client(self) -> MenuServiceClient:
        """Create a mock MenuServiceClient."""
        return MagicMock(spec=MenuServiceClient)

    @pytest.fixture
    def mock_status_repo(self) -> SyncStatusRepository:
        """Create a mock SyncStatusRepository."""
        return MagicMock(spec=SyncStatusRepository)

    @pytest.fixture
    def mock_adapter(self) -> PlatformAdapter:
        """Create a mock PlatformAdapter."""
        adapter = MagicMock(spec=PlatformAdapter)
        adapter.format_menu = MagicMock(return_value={"menu": "data"})
        adapter.publish_menu = AsyncMock(return_value=True)
        return adapter

    @pytest.fixture
    def sync_service(
        self,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
    ) -> SyncService:
        """Create a SyncService with mocked dependencies."""
        return SyncService(
            menu_service_client=mock_menu_client,
            status_repository=mock_status_repo,
        )

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
            ),
            MenuItem(
                id="item_2",
                restaurant_id="rest_123",
                name="Salad",
                description="Fresh salad",
                price=Decimal("9.99"),
                category_id="cat_2",
                available=True,
                image_url=None,
            ),
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
            ),
            Category(
                id="cat_2",
                restaurant_id="rest_123",
                name="Sides",
                description="Side dishes",
                sort_order=2,
            ),
        ]

    def test_service_initialization(
        self,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
    ) -> None:
        """Test that service initializes correctly."""
        service = SyncService(
            menu_service_client=mock_menu_client,
            status_repository=mock_status_repo,
        )
        assert service.menu_service_client == mock_menu_client
        assert service.status_repository == mock_status_repo

    @pytest.mark.asyncio
    async def test_sync_to_platform_success(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test successful sync to a single platform."""
        # Mock menu data fetch
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
        )

        assert result.success is True
        assert result.platform == "doordash"
        assert result.item_count == 2
        assert result.error_message is None

        # Verify menu data was fetched
        mock_menu_client.get_menu_data.assert_called_once_with("rest_123")

        # Verify adapter was called
        mock_adapter.format_menu.assert_called_once()
        mock_adapter.publish_menu.assert_called_once()

        # Verify status was saved
        mock_status_repo.save_status.assert_called_once()
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.restaurant_id == "rest_123"
        assert saved_status.platform == "doordash"
        assert saved_status.status == SyncStatusEnum.COMPLETED
        assert saved_status.item_count == 2

    @pytest.mark.asyncio
    async def test_sync_to_platform_menu_fetch_failure(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
    ) -> None:
        """Test sync fails when menu data fetch fails."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=None)
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
        )

        assert result.success is False
        assert result.platform == "doordash"
        assert result.item_count == 0
        assert "Failed to fetch menu data" in result.error_message

        # Verify adapter was not called
        mock_adapter.format_menu.assert_not_called()
        mock_adapter.publish_menu.assert_not_called()

        # Verify failed status was saved
        mock_status_repo.save_status.assert_called_once()
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.status == SyncStatusEnum.FAILED

    @pytest.mark.asyncio
    async def test_sync_to_platform_format_failure(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test sync fails when menu formatting fails."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_adapter.format_menu = MagicMock(return_value=None)  # Format failure
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
        )

        assert result.success is False
        assert "Failed to format menu" in result.error_message

        # Verify publish was not called
        mock_adapter.publish_menu.assert_not_called()

        # Verify failed status was saved
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.status == SyncStatusEnum.FAILED

    @pytest.mark.asyncio
    async def test_sync_to_platform_publish_failure(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test sync fails when publishing to platform fails."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_adapter.publish_menu = AsyncMock(return_value=False)  # Publish failure
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
        )

        assert result.success is False
        assert "Failed to publish menu" in result.error_message

        # Verify failed status was saved
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.status == SyncStatusEnum.FAILED

    @pytest.mark.asyncio
    async def test_sync_to_platform_with_retry_success(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that sync retries once and succeeds on second attempt."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        # First publish fails, second succeeds
        mock_adapter.publish_menu = AsyncMock(side_effect=[False, True])
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
            retry=True,
        )

        assert result.success is True
        assert mock_adapter.publish_menu.call_count == 2

        # Verify successful status was saved
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.status == SyncStatusEnum.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_to_platform_with_retry_failure(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that sync retries once and fails after both attempts."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        # Both publish attempts fail
        mock_adapter.publish_menu = AsyncMock(return_value=False)
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
            retry=True,
        )

        assert result.success is False
        assert mock_adapter.publish_menu.call_count == 2

        # Verify failed status was saved
        saved_status = mock_status_repo.save_status.call_args[0][0]
        assert saved_status.status == SyncStatusEnum.FAILED

    @pytest.mark.asyncio
    async def test_sync_to_platform_without_retry(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        mock_adapter: PlatformAdapter,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that sync does not retry when retry=False."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_adapter.publish_menu = AsyncMock(return_value=False)
        mock_status_repo.save_status = MagicMock(return_value=True)

        result = await sync_service.sync_to_platform(
            restaurant_id="rest_123",
            platform="doordash",
            adapter=mock_adapter,
            retry=False,
        )

        assert result.success is False
        # Only one attempt, no retry
        assert mock_adapter.publish_menu.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_to_multiple_platforms(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test syncing to multiple platforms concurrently."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_status_repo.save_status = MagicMock(return_value=True)

        # Create two mock adapters
        adapter1 = MagicMock(spec=PlatformAdapter)
        adapter1.format_menu = MagicMock(return_value={"menu": "data1"})
        adapter1.publish_menu = AsyncMock(return_value=True)

        adapter2 = MagicMock(spec=PlatformAdapter)
        adapter2.format_menu = MagicMock(return_value={"menu": "data2"})
        adapter2.publish_menu = AsyncMock(return_value=True)

        platform_adapters = {
            "doordash": adapter1,
            "ubereats": adapter2,
        }

        results = await sync_service.sync_to_multiple_platforms(
            restaurant_id="rest_123",
            platform_adapters=platform_adapters,
        )

        assert len(results) == 2
        assert all(r.success for r in results)
        assert {r.platform for r in results} == {"doordash", "ubereats"}

        # Verify both adapters were called
        adapter1.publish_menu.assert_called_once()
        adapter2.publish_menu.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_to_multiple_platforms_partial_failure(
        self,
        sync_service: SyncService,
        mock_menu_client: MenuServiceClient,
        mock_status_repo: SyncStatusRepository,
        sample_items: list[MenuItem],
        sample_categories: list[Category],
    ) -> None:
        """Test that one platform failing doesn't affect others."""
        mock_menu_client.get_menu_data = AsyncMock(return_value=(sample_items, sample_categories))
        mock_status_repo.save_status = MagicMock(return_value=True)

        # Create two adapters - one succeeds, one fails
        adapter1 = MagicMock(spec=PlatformAdapter)
        adapter1.format_menu = MagicMock(return_value={"menu": "data1"})
        adapter1.publish_menu = AsyncMock(return_value=True)

        adapter2 = MagicMock(spec=PlatformAdapter)
        adapter2.format_menu = MagicMock(return_value={"menu": "data2"})
        adapter2.publish_menu = AsyncMock(return_value=False)  # This one fails

        platform_adapters = {
            "doordash": adapter1,
            "ubereats": adapter2,
        }

        results = await sync_service.sync_to_multiple_platforms(
            restaurant_id="rest_123",
            platform_adapters=platform_adapters,
        )

        assert len(results) == 2
        success_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        assert len(success_results) == 1
        assert len(failed_results) == 1
        assert success_results[0].platform == "doordash"
        assert failed_results[0].platform == "ubereats"

    @pytest.mark.asyncio
    async def test_get_sync_status(
        self,
        sync_service: SyncService,
        mock_status_repo: SyncStatusRepository,
    ) -> None:
        """Test retrieving sync status for a restaurant and platform."""
        mock_status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
            last_sync_time=datetime.now(UTC),
            item_count=42,
            external_menu_id="ext_123",
        )
        mock_status_repo.get_status = MagicMock(return_value=mock_status)

        status = await sync_service.get_sync_status("rest_123", "doordash")

        assert status == mock_status
        mock_status_repo.get_status.assert_called_once_with("rest_123", "doordash")

    @pytest.mark.asyncio
    async def test_get_sync_status_not_found(
        self,
        sync_service: SyncService,
        mock_status_repo: SyncStatusRepository,
    ) -> None:
        """Test retrieving sync status returns None when not found."""
        mock_status_repo.get_status = MagicMock(return_value=None)

        status = await sync_service.get_sync_status("rest_123", "doordash")

        assert status is None

    @pytest.mark.asyncio
    async def test_get_all_statuses_for_restaurant(
        self,
        sync_service: SyncService,
        mock_status_repo: SyncStatusRepository,
    ) -> None:
        """Test retrieving all sync statuses for a restaurant."""
        mock_statuses = [
            SyncStatus(
                restaurant_id="rest_123",
                platform="doordash",
                status=SyncStatusEnum.COMPLETED,
                last_sync_time=datetime.now(UTC),
                item_count=42,
                external_menu_id="ext_123",
            ),
            SyncStatus(
                restaurant_id="rest_123",
                platform="ubereats",
                status=SyncStatusEnum.FAILED,
                last_sync_time=datetime.now(UTC),
                item_count=0,
                external_menu_id=None,
            ),
        ]
        mock_status_repo.list_statuses_for_restaurant = MagicMock(return_value=mock_statuses)

        statuses = await sync_service.get_all_statuses_for_restaurant("rest_123")

        assert len(statuses) == 2
        assert statuses == mock_statuses
        mock_status_repo.list_statuses_for_restaurant.assert_called_once_with("rest_123")
