"""Error service for managing sync errors and retry logic."""

import logging
import uuid
from datetime import UTC, datetime

from restaurant_sync_service.models.menu_models import Category, MenuItem
from restaurant_sync_service.models.sync_models import SyncError
from restaurant_sync_service.repositories.sync_repositories import SyncErrorRepository

logger = logging.getLogger(__name__)


class ErrorService:
    """Service for managing sync errors and error queue.

    This service handles recording sync failures, tracking retry attempts,
    and providing access to error history for manual intervention via the
    admin dashboard.
    """

    def __init__(self, error_repository: SyncErrorRepository) -> None:
        """Initialize the ErrorService.

        Args:
            error_repository: Repository for storing sync errors
        """
        self.error_repository = error_repository

    async def record_sync_error(
        self,
        restaurant_id: str,
        platform: str,
        error_details: str,
        menu_items: list[MenuItem] | None = None,
        menu_categories: list[Category] | None = None,
    ) -> str | None:
        """Record a sync error to the error queue.

        Args:
            restaurant_id: The restaurant that failed to sync
            platform: The platform that failed
            error_details: Description of the error
            menu_items: Optional snapshot of menu items at time of failure
            menu_categories: Optional snapshot of categories at time of failure

        Returns:
            The error ID if saved successfully, None otherwise
        """
        error_id = f"err_{uuid.uuid4().hex[:12]}"

        # Create menu snapshot if items/categories provided
        menu_snapshot = None
        if menu_items is not None and menu_categories is not None:
            menu_snapshot = self._create_menu_snapshot(menu_items, menu_categories)

        error = SyncError(
            error_id=error_id,
            created_at=datetime.now(UTC),
            restaurant_id=restaurant_id,
            platform=platform,
            error_details=error_details,
            menu_snapshot=menu_snapshot,
            retry_count=0,
        )

        success = self.error_repository.save_error(error)
        return error_id if success else None

    async def get_error(self, error_id: str) -> SyncError | None:
        """Get a specific error by ID.

        Args:
            error_id: The error ID to retrieve

        Returns:
            SyncError if found, None otherwise
        """
        return self.error_repository.get_error(error_id)

    async def get_errors_for_restaurant(
        self,
        restaurant_id: str,
        platform: str | None = None,
        limit: int | None = None,
    ) -> list[SyncError]:
        """Get all errors for a restaurant, optionally filtered by platform.

        Args:
            restaurant_id: The restaurant ID
            platform: Optional platform to filter by
            limit: Optional limit on number of errors to return

        Returns:
            List of SyncError objects, empty list if none found
        """
        errors = self.error_repository.list_errors_for_restaurant(
            restaurant_id=restaurant_id,
            limit=limit,
        )

        # Filter by platform if specified
        if platform and errors:
            errors = [e for e in errors if e.platform == platform]

        return errors if errors else []

    async def increment_retry_count(self, error_id: str) -> bool:
        """Increment the retry count for an error.

        This should be called each time a manual retry is attempted
        via the admin dashboard.

        Args:
            error_id: The error ID to update

        Returns:
            True if updated successfully, False otherwise
        """
        # Get current error to determine current retry count
        error = self.error_repository.get_error(error_id)
        if not error:
            return False

        new_retry_count = error.retry_count + 1
        return self.error_repository.update_retry_count(error_id, new_retry_count)

    def _create_menu_snapshot(
        self,
        items: list[MenuItem],
        categories: list[Category],
    ) -> dict:
        """Create a JSON-serializable snapshot of menu data.

        Args:
            items: Menu items to snapshot
            categories: Categories to snapshot

        Returns:
            Dictionary with serialized menu data
        """
        return {
            "items": [self._serialize_menu_item(item) for item in items],
            "categories": [self._serialize_category(cat) for cat in categories],
        }

    def _serialize_menu_item(self, item: MenuItem) -> dict:
        """Serialize a MenuItem to a dictionary.

        Args:
            item: MenuItem to serialize

        Returns:
            Dictionary representation of the item
        """
        return {
            "id": item.id,
            "restaurant_id": item.restaurant_id,
            "name": item.name,
            "description": item.description,
            "price": str(item.price),  # Convert Decimal to string for JSON
            "category_id": item.category_id,
            "available": item.available,
            "image_url": item.image_url,
        }

    def _serialize_category(self, category: Category) -> dict:
        """Serialize a Category to a dictionary.

        Args:
            category: Category to serialize

        Returns:
            Dictionary representation of the category
        """
        return {
            "id": category.id,
            "restaurant_id": category.restaurant_id,
            "name": category.name,
            "description": category.description,
            "sort_order": category.sort_order,
        }