"""Unit tests for AWS Lambda handler."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.lambda_handler import handle_eventbridge_event, is_eventbridge_event, lambda_handler


@pytest.mark.unit
class TestIsEventBridgeEvent:
    """Tests for is_eventbridge_event function."""

    def test_returns_true_for_eventbridge_event(self) -> None:
        """Test that EventBridge events are correctly identified."""
        event = {
            "version": "0",
            "id": "event-id",
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {"restaurant_id": "rest123"},
        }

        assert is_eventbridge_event(event) is True

    def test_returns_false_for_api_gateway_http_event(self) -> None:
        """Test that API Gateway HTTP events are correctly identified."""
        event = {
            "version": "2.0",
            "requestContext": {
                "http": {"method": "GET", "path": "/health"},
                "requestId": "request-id",
            },
            "rawPath": "/health",
        }

        assert is_eventbridge_event(event) is False

    def test_returns_false_for_api_gateway_rest_event(self) -> None:
        """Test that API Gateway REST events are correctly identified."""
        event = {
            "requestContext": {
                "requestId": "request-id",
                "apiId": "api-id",
            },
            "path": "/health",
            "httpMethod": "GET",
        }

        assert is_eventbridge_event(event) is False

    def test_returns_false_for_malformed_event(self) -> None:
        """Test that malformed events return False."""
        event = {"random": "data"}

        assert is_eventbridge_event(event) is False


@pytest.mark.unit
class TestHandleEventBridgeEvent:
    """Tests for handle_eventbridge_event function."""

    @patch("src.lambda_handler.get_event_handler")
    def test_processes_valid_menu_changed_event(self, mock_get_handler: Mock) -> None:
        """Test that valid MenuChanged events are processed successfully."""
        mock_handler = MagicMock()
        mock_handler.handle_menu_changed = AsyncMock(return_value=True)
        mock_get_handler.return_value = mock_handler

        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {
                "restaurant_id": "rest123",
                "event_type": "menu.updated",
                "timestamp": "2024-01-15T10:00:00Z",
            },
        }

        result = handle_eventbridge_event(event)

        assert result["statusCode"] == 200
        assert "rest123" in result["body"]
        mock_handler.handle_menu_changed.assert_called_once()

    @patch("src.lambda_handler.get_event_handler")
    def test_returns_error_when_sync_fails(self, mock_get_handler: Mock) -> None:
        """Test that error response is returned when sync fails."""
        mock_handler = MagicMock()
        mock_handler.handle_menu_changed = AsyncMock(return_value=False)
        mock_get_handler.return_value = mock_handler

        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {
                "restaurant_id": "rest123",
                "menu_version": "v2",
                "changed_at": "2024-01-15T10:00:00Z",
            },
        }

        result = handle_eventbridge_event(event)

        assert result["statusCode"] == 500
        assert "Failed" in result["body"]

    def test_returns_error_for_unsupported_event_source(self) -> None:
        """Test that unsupported event sources are rejected."""
        event = {
            "source": "com.other.service",
            "detail-type": "SomeEvent",
            "detail": {},
        }

        result = handle_eventbridge_event(event)

        assert result["statusCode"] == 400
        assert "Unsupported event type" in result["body"]

    def test_returns_error_for_unsupported_event_type(self) -> None:
        """Test that unsupported event types are rejected."""
        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuDeleted",
            "detail": {},
        }

        result = handle_eventbridge_event(event)

        assert result["statusCode"] == 400
        assert "Unsupported event type" in result["body"]

    @patch("src.lambda_handler.get_event_handler")
    def test_handles_exception_during_processing(self, mock_get_handler: Mock) -> None:
        """Test that exceptions during event processing are handled gracefully."""
        mock_handler = MagicMock()
        mock_handler.handle_menu_changed.side_effect = Exception("Processing error")
        mock_get_handler.return_value = mock_handler

        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {
                "restaurant_id": "rest123",
                "menu_version": "v2",
                "changed_at": "2024-01-15T10:00:00Z",
            },
        }

        result = handle_eventbridge_event(event)

        assert result["statusCode"] == 500
        assert "Error processing event" in result["body"]


@pytest.mark.unit
class TestLambdaHandler:
    """Tests for main lambda_handler function."""

    @patch("src.lambda_handler.handle_eventbridge_event")
    def test_routes_eventbridge_events_to_handler(self, mock_handle_eventbridge: Mock) -> None:
        """Test that EventBridge events are routed to the correct handler."""
        mock_handle_eventbridge.return_value = {
            "statusCode": 200,
            "body": "Success",
        }

        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {"restaurant_id": "rest123"},
        }
        context = MagicMock()
        context.request_id = "test-request-id"

        result = lambda_handler(event, context)

        assert result["statusCode"] == 200
        mock_handle_eventbridge.assert_called_once_with(event)

    @patch("src.lambda_handler.mangum_handler")
    def test_routes_api_gateway_events_to_mangum(self, mock_mangum_handler: Mock) -> None:
        """Test that API Gateway events are routed to Mangum."""
        mock_mangum_handler.return_value = {
            "statusCode": 200,
            "body": '{"status": "ok"}',
        }

        event = {
            "version": "2.0",
            "requestContext": {
                "http": {"method": "GET", "path": "/health"},
                "requestId": "request-id",
            },
            "rawPath": "/health",
        }
        context = MagicMock()
        context.request_id = "test-request-id"

        result = lambda_handler(event, context)

        assert result["statusCode"] == 200
        mock_mangum_handler.assert_called_once_with(event, context)

    @patch("src.lambda_handler.handle_eventbridge_event")
    def test_handles_unhandled_exceptions(self, mock_handle_eventbridge: Mock) -> None:
        """Test that unhandled exceptions are caught and returned as 500 errors."""
        mock_handle_eventbridge.side_effect = Exception("Unexpected error")

        event = {
            "source": "com.restaurant.menu",
            "detail-type": "MenuChanged",
            "detail": {},
        }
        context = MagicMock()
        context.request_id = "test-request-id"

        result = lambda_handler(event, context)

        assert result["statusCode"] == 500
        assert "Internal server error" in result["body"]
