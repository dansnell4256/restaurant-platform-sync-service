"""Unit tests for EventBridge event handler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.handlers.event_handler import (
    EventHandler,
    MenuChangedEvent,
    parse_eventbridge_event,
)
from restaurant_sync_service.services.error_service import ErrorService
from restaurant_sync_service.services.sync_service import SyncResult, SyncService


@pytest.mark.unit
class TestMenuChangedEvent:
    """Test suite for MenuChangedEvent model."""

    def test_event_creation(self) -> None:
        """Test creating a menu changed event."""
        event = MenuChangedEvent(
            restaurant_id="rest_123",
            event_type="menu.updated",
            timestamp="2025-01-15T10:30:00Z",
        )
        assert event.restaurant_id == "rest_123"
        assert event.event_type == "menu.updated"
        assert event.timestamp == "2025-01-15T10:30:00Z"

    def test_event_from_dict(self) -> None:
        """Test creating event from dictionary."""
        data = {
            "restaurant_id": "rest_456",
            "event_type": "menu.created",
            "timestamp": "2025-01-15T11:00:00Z",
        }
        event = MenuChangedEvent(**data)
        assert event.restaurant_id == "rest_456"
        assert event.event_type == "menu.created"


@pytest.mark.unit
class TestParseEventBridgeEvent:
    """Test suite for EventBridge event parsing."""

    def test_parse_valid_event(self) -> None:
        """Test parsing a valid EventBridge event."""
        eventbridge_event = {
            "version": "0",
            "id": "event-123",
            "detail-type": "Menu Changed",
            "source": "menu-service",
            "account": "123456789012",
            "time": "2025-01-15T10:30:00Z",
            "region": "us-east-1",
            "detail": {
                "restaurant_id": "rest_123",
                "event_type": "menu.updated",
                "timestamp": "2025-01-15T10:30:00Z",
            },
        }

        event = parse_eventbridge_event(eventbridge_event)

        assert event is not None
        assert event.restaurant_id == "rest_123"
        assert event.event_type == "menu.updated"
        assert event.timestamp == "2025-01-15T10:30:00Z"

    def test_parse_event_missing_detail(self) -> None:
        """Test parsing event with missing detail field."""
        eventbridge_event = {
            "version": "0",
            "id": "event-123",
            "detail-type": "Menu Changed",
        }

        event = parse_eventbridge_event(eventbridge_event)
        assert event is None

    def test_parse_event_invalid_detail(self) -> None:
        """Test parsing event with invalid detail structure."""
        eventbridge_event = {
            "version": "0",
            "detail": {
                "invalid_field": "value",
            },
        }

        event = parse_eventbridge_event(eventbridge_event)
        assert event is None


@pytest.mark.unit
class TestEventHandler:
    """Test suite for EventHandler."""

    @pytest.fixture
    def mock_sync_service(self) -> SyncService:
        """Create a mock SyncService."""
        return MagicMock(spec=SyncService)

    @pytest.fixture
    def mock_error_service(self) -> ErrorService:
        """Create a mock ErrorService."""
        return MagicMock(spec=ErrorService)

    @pytest.fixture
    def mock_adapters(self) -> dict[str, PlatformAdapter]:
        """Create mock platform adapters."""
        adapter1 = MagicMock(spec=PlatformAdapter)
        adapter2 = MagicMock(spec=PlatformAdapter)
        return {
            "doordash": adapter1,
            "ubereats": adapter2,
        }

    @pytest.fixture
    def event_handler(
        self,
        mock_sync_service: SyncService,
        mock_error_service: ErrorService,
        mock_adapters: dict[str, PlatformAdapter],
    ) -> EventHandler:
        """Create an EventHandler with mocked dependencies."""
        return EventHandler(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
        )

    def test_handler_initialization(
        self,
        mock_sync_service: SyncService,
        mock_error_service: ErrorService,
        mock_adapters: dict[str, PlatformAdapter],
    ) -> None:
        """Test that handler initializes correctly."""
        handler = EventHandler(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
        )
        assert handler.sync_service == mock_sync_service
        assert handler.error_service == mock_error_service
        assert handler.platform_adapters == mock_adapters

    @pytest.mark.asyncio
    async def test_handle_menu_changed_success(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
    ) -> None:
        """Test successfully handling a menu changed event."""
        event = MenuChangedEvent(
            restaurant_id="rest_123",
            event_type="menu.updated",
            timestamp="2025-01-15T10:30:00Z",
        )

        # Mock successful sync to both platforms
        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
                SyncResult(success=True, platform="ubereats", item_count=10),
            ]
        )

        result = await event_handler.handle_menu_changed(event)

        assert result is True
        mock_sync_service.sync_to_multiple_platforms.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_menu_changed_partial_failure(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
        mock_error_service: ErrorService,
    ) -> None:
        """Test handling event when one platform fails."""
        event = MenuChangedEvent(
            restaurant_id="rest_123",
            event_type="menu.updated",
            timestamp="2025-01-15T10:30:00Z",
        )

        # Mock one success, one failure
        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
                SyncResult(
                    success=False,
                    platform="ubereats",
                    item_count=0,
                    error_message="Failed to publish",
                ),
            ]
        )
        mock_error_service.record_sync_error = AsyncMock(return_value="err_123")

        result = await event_handler.handle_menu_changed(event)

        # Returns True because at least one platform succeeded
        assert result is True
        # Error should be recorded for failed platform
        mock_error_service.record_sync_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_menu_changed_all_failures(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
        mock_error_service: ErrorService,
    ) -> None:
        """Test handling event when all platforms fail."""
        event = MenuChangedEvent(
            restaurant_id="rest_123",
            event_type="menu.updated",
            timestamp="2025-01-15T10:30:00Z",
        )

        # Mock all failures
        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(
                    success=False,
                    platform="doordash",
                    item_count=0,
                    error_message="Failed to publish",
                ),
                SyncResult(
                    success=False,
                    platform="ubereats",
                    item_count=0,
                    error_message="Failed to publish",
                ),
            ]
        )
        mock_error_service.record_sync_error = AsyncMock(return_value="err_123")

        result = await event_handler.handle_menu_changed(event)

        # Returns False when all platforms fail
        assert result is False
        # Errors recorded for both platforms
        assert mock_error_service.record_sync_error.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_eventbridge_event_success(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
    ) -> None:
        """Test handling a complete EventBridge event."""
        eventbridge_event = {
            "version": "0",
            "id": "event-123",
            "detail-type": "Menu Changed",
            "source": "menu-service",
            "detail": {
                "restaurant_id": "rest_123",
                "event_type": "menu.updated",
                "timestamp": "2025-01-15T10:30:00Z",
            },
        }

        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
            ]
        )

        result = await event_handler.handle_eventbridge_event(eventbridge_event, {})

        assert result == {
            "statusCode": 200,
            "body": "Successfully processed menu change for restaurant rest_123",
        }

    @pytest.mark.asyncio
    async def test_handle_eventbridge_event_invalid_event(
        self,
        event_handler: EventHandler,
    ) -> None:
        """Test handling an invalid EventBridge event."""
        eventbridge_event = {
            "version": "0",
            "detail": {},  # Missing required fields
        }

        result = await event_handler.handle_eventbridge_event(eventbridge_event, {})

        assert result == {
            "statusCode": 400,
            "body": "Invalid event format",
        }

    @pytest.mark.asyncio
    async def test_handle_eventbridge_event_sync_failure(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
        mock_error_service: ErrorService,
    ) -> None:
        """Test handling EventBridge event when sync fails."""
        eventbridge_event = {
            "version": "0",
            "detail": {
                "restaurant_id": "rest_123",
                "event_type": "menu.updated",
                "timestamp": "2025-01-15T10:30:00Z",
            },
        }

        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(
                    success=False,
                    platform="doordash",
                    item_count=0,
                    error_message="Failed",
                ),
            ]
        )
        mock_error_service.record_sync_error = AsyncMock(return_value="err_123")

        result = await event_handler.handle_eventbridge_event(eventbridge_event, {})

        assert result == {
            "statusCode": 500,
            "body": "Failed to sync menu for restaurant rest_123",
        }

    @pytest.mark.asyncio
    async def test_handle_menu_changed_with_retry(
        self,
        event_handler: EventHandler,
        mock_sync_service: SyncService,
    ) -> None:
        """Test that sync is called with retry enabled."""
        event = MenuChangedEvent(
            restaurant_id="rest_123",
            event_type="menu.updated",
            timestamp="2025-01-15T10:30:00Z",
        )

        mock_sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
            ]
        )

        await event_handler.handle_menu_changed(event)

        # Verify retry=True is passed
        call_kwargs = mock_sync_service.sync_to_multiple_platforms.call_args.kwargs
        assert call_kwargs.get("retry") is True
