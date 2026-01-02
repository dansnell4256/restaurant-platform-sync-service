"""Sync service for orchestrating menu synchronization to platforms."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.models.sync_models import SyncStatus, SyncStatusEnum
from restaurant_sync_service.repositories.sync_repositories import (
    SyncStatusRepository,
)
from restaurant_sync_service.services.menu_service_client import MenuServiceClient

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation to a single platform.

    Attributes:
        success: Whether the sync completed successfully
        platform: The platform that was synced to
        item_count: Number of menu items synced
        error_message: Error message if sync failed, None otherwise
    """

    success: bool
    platform: str
    item_count: int
    error_message: str | None = None


class SyncService:
    """Service for orchestrating menu synchronization to delivery platforms.

    This service coordinates fetching menu data from the menu service,
    formatting it for each platform, publishing to platform APIs, and
    recording sync status in DynamoDB.
    """

    def __init__(
        self,
        menu_service_client: MenuServiceClient,
        status_repository: SyncStatusRepository,
        retry_delay_seconds: int = 2,
    ) -> None:
        """Initialize the SyncService.

        Args:
            menu_service_client: Client for fetching menu data
            status_repository: Repository for storing sync status
            retry_delay_seconds: Seconds to wait between retry attempts
        """
        self.menu_service_client = menu_service_client
        self.status_repository = status_repository
        self.retry_delay_seconds = retry_delay_seconds

    async def sync_to_platform(
        self,
        restaurant_id: str,
        platform: str,
        adapter: PlatformAdapter,
        retry: bool = True,
    ) -> SyncResult:
        """Sync menu data to a single platform.

        This method orchestrates the complete sync flow:
        1. Fetch menu data from menu service
        2. Format menu for the platform
        3. Publish to platform API (with optional retry)
        4. Record sync status in DynamoDB

        Args:
            restaurant_id: The restaurant to sync
            platform: Platform name (e.g., "doordash", "ubereats")
            adapter: Platform adapter for formatting and publishing
            retry: Whether to retry once on failure (default: True)

        Returns:
            SyncResult indicating success/failure and details
        """
        # Step 1: Fetch menu data
        menu_data = await self.menu_service_client.get_menu_data(restaurant_id)
        if menu_data is None:
            error_msg = f"Failed to fetch menu data for restaurant {restaurant_id}"
            logger.error(error_msg)  # pragma: no cover
            await self._save_failed_status(restaurant_id, platform, 0)
            return SyncResult(
                success=False,
                platform=platform,
                item_count=0,
                error_message=error_msg,
            )

        items, categories = menu_data

        # Step 2: Format menu for platform
        formatted_menu = adapter.format_menu(items, categories)
        if formatted_menu is None:
            error_msg = f"Failed to format menu for platform {platform}"
            logger.error(error_msg)  # pragma: no cover
            await self._save_failed_status(restaurant_id, platform, len(items))
            return SyncResult(
                success=False,
                platform=platform,
                item_count=len(items),
                error_message=error_msg,
            )

        # Step 3: Publish to platform (with retry logic)
        publish_success = await adapter.publish_menu(restaurant_id, formatted_menu)

        if not publish_success and retry:
            logger.warning(
                f"First publish attempt failed for {platform}, retrying..."
            )  # pragma: no cover
            await asyncio.sleep(self.retry_delay_seconds)
            publish_success = await adapter.publish_menu(restaurant_id, formatted_menu)

        # Step 4: Record sync status
        if publish_success:
            await self._save_success_status(restaurant_id, platform, len(items))
            return SyncResult(
                success=True,
                platform=platform,
                item_count=len(items),
            )
        else:
            error_msg = f"Failed to publish menu to {platform} after all retry attempts"
            logger.error(error_msg)  # pragma: no cover
            await self._save_failed_status(restaurant_id, platform, len(items))
            return SyncResult(
                success=False,
                platform=platform,
                item_count=len(items),
                error_message=error_msg,
            )

    async def sync_to_multiple_platforms(
        self,
        restaurant_id: str,
        platform_adapters: dict[str, PlatformAdapter],
        retry: bool = True,
    ) -> list[SyncResult]:
        """Sync menu data to multiple platforms concurrently.

        Args:
            restaurant_id: The restaurant to sync
            platform_adapters: Dictionary mapping platform names to their adapters
            retry: Whether to retry once on failure (default: True)

        Returns:
            List of SyncResult for each platform
        """
        tasks = []
        for platform, adapter in platform_adapters.items():
            task = self.sync_to_platform(
                restaurant_id=restaurant_id,
                platform=platform,
                adapter=adapter,
                retry=retry,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return list(results)

    async def get_sync_status(
        self,
        restaurant_id: str,
        platform: str,
    ) -> SyncStatus | None:
        """Get the sync status for a restaurant and platform.

        Args:
            restaurant_id: The restaurant ID
            platform: The platform name

        Returns:
            SyncStatus if found, None otherwise
        """
        return self.status_repository.get_status(restaurant_id, platform)

    async def get_all_statuses_for_restaurant(
        self,
        restaurant_id: str,
    ) -> list[SyncStatus]:
        """Get all sync statuses for a restaurant across all platforms.

        Args:
            restaurant_id: The restaurant ID

        Returns:
            List of SyncStatus for all platforms, empty list if none found
        """
        statuses = self.status_repository.list_statuses_for_restaurant(restaurant_id)
        return statuses if statuses else []

    async def _save_success_status(
        self,
        restaurant_id: str,
        platform: str,
        item_count: int,
    ) -> None:
        """Save a successful sync status to the repository.

        Args:
            restaurant_id: The restaurant ID
            platform: The platform name
            item_count: Number of items synced
        """
        status = SyncStatus(
            restaurant_id=restaurant_id,
            platform=platform,
            status=SyncStatusEnum.COMPLETED,
            last_sync_time=datetime.now(UTC),
            item_count=item_count,
            external_menu_id=None,  # Could be set by adapter in future
        )
        self.status_repository.save_status(status)

    async def _save_failed_status(
        self,
        restaurant_id: str,
        platform: str,
        item_count: int,
    ) -> None:
        """Save a failed sync status to the repository.

        Args:
            restaurant_id: The restaurant ID
            platform: The platform name
            item_count: Number of items attempted to sync
        """
        status = SyncStatus(
            restaurant_id=restaurant_id,
            platform=platform,
            status=SyncStatusEnum.FAILED,
            last_sync_time=datetime.now(UTC),
            item_count=item_count,
            external_menu_id=None,
        )
        self.status_repository.save_status(status)
