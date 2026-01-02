"""EventBridge event handler for menu change events."""

import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.services.error_service import ErrorService
from restaurant_sync_service.services.sync_service import SyncService

logger = logging.getLogger(__name__)


class MenuChangedEvent(BaseModel):
    """Model for menu changed events from EventBridge.

    Attributes:
        restaurant_id: The restaurant whose menu changed
        event_type: Type of change (menu.created, menu.updated, menu.deleted)
        timestamp: ISO 8601 timestamp of when the event occurred
    """

    restaurant_id: str
    event_type: str
    timestamp: str


def parse_eventbridge_event(event: dict[str, Any]) -> MenuChangedEvent | None:
    """Parse an EventBridge event into a MenuChangedEvent.

    Args:
        event: Raw EventBridge event dictionary

    Returns:
        MenuChangedEvent if parsing succeeds, None otherwise
    """
    try:
        detail = event.get("detail", {})
        return MenuChangedEvent(**detail)
    except (ValidationError, TypeError) as e:
        logger.error(f"Failed to parse EventBridge event: {e}")  # pragma: no cover
        return None


class EventHandler:
    """Handler for processing EventBridge menu change events.

    This handler coordinates the sync process when menu changes are detected.
    It orchestrates syncing to multiple platforms concurrently and records
    any errors that occur.
    """

    def __init__(
        self,
        sync_service: SyncService,
        error_service: ErrorService,
        platform_adapters: dict[str, PlatformAdapter],
    ) -> None:
        """Initialize the event handler.

        Args:
            sync_service: Service for orchestrating menu syncs
            error_service: Service for recording sync errors
            platform_adapters: Dictionary mapping platform names to their adapters
        """
        self.sync_service = sync_service
        self.error_service = error_service
        self.platform_adapters = platform_adapters

    async def handle_menu_changed(self, event: MenuChangedEvent) -> bool:
        """Handle a menu changed event.

        Syncs the menu to all configured platforms and records any errors.

        Args:
            event: The menu changed event to process

        Returns:
            True if at least one platform synced successfully, False if all failed
        """
        logger.info(
            f"Processing menu change for restaurant {event.restaurant_id}: {event.event_type}"
        )

        # Sync to all platforms concurrently with retry enabled
        results = await self.sync_service.sync_to_multiple_platforms(
            restaurant_id=event.restaurant_id,
            platform_adapters=self.platform_adapters,
            retry=True,
        )

        # Track successes and failures
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        # Log results
        if successes:
            platforms = ", ".join(r.platform for r in successes)
            logger.info(f"Successfully synced restaurant {event.restaurant_id} to: {platforms}")

        # Record errors for failed platforms
        for failure in failures:
            logger.error(
                f"Failed to sync restaurant {event.restaurant_id} to {failure.platform}: "
                f"{failure.error_message}"
            )  # pragma: no cover
            await self.error_service.record_sync_error(
                restaurant_id=event.restaurant_id,
                platform=failure.platform,
                error_details=failure.error_message or "Unknown error",
            )

        # Return True if at least one platform succeeded
        return len(successes) > 0

    async def handle_eventbridge_event(
        self, event: dict[str, Any], _context: Any
    ) -> dict[str, Any]:
        """Lambda handler for EventBridge events.

        This is the entry point for AWS Lambda when triggered by EventBridge.

        Args:
            event: EventBridge event dictionary
            _context: Lambda context object (unused)

        Returns:
            Dictionary with statusCode and body for Lambda response
        """
        # Parse the event
        menu_event = parse_eventbridge_event(event)
        if not menu_event:
            logger.error("Received invalid event format")  # pragma: no cover
            return {
                "statusCode": 400,
                "body": "Invalid event format",
            }

        # Process the event
        success = await self.handle_menu_changed(menu_event)

        if success:
            return {
                "statusCode": 200,
                "body": f"Successfully processed menu change for restaurant {menu_event.restaurant_id}",
            }
        else:
            return {
                "statusCode": 500,
                "body": f"Failed to sync menu for restaurant {menu_event.restaurant_id}",
            }
