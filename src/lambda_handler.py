"""AWS Lambda handler for both API Gateway and EventBridge events.

This module provides a single Lambda entry point that handles:
1. API Gateway requests (via Mangum ASGI adapter for FastAPI)
2. EventBridge menu change events (direct handling)

The handler automatically detects the event type and routes accordingly.
"""

import asyncio
import logging
from typing import Any

from mangum import Mangum

from lambda_dependencies import get_event_handler, get_fastapi_app, initialize_lambda_environment
from restaurant_sync_service.handlers.event_handler import MenuChangedEvent

# Initialize Lambda environment during cold start (skip in test mode)
import os

if os.getenv("ENVIRONMENT") != "test":
    initialize_lambda_environment()

logger = logging.getLogger(__name__)

# Create FastAPI app and Mangum adapter (cached for warm starts, skip in test mode)
if os.getenv("ENVIRONMENT") != "test":
    app = get_fastapi_app()
    mangum_handler = Mangum(app, lifespan="off")
else:
    app = None  # type: ignore
    mangum_handler = None  # type: ignore


def is_eventbridge_event(event: dict[str, Any]) -> bool:
    """Determine if the event is from EventBridge.

    Args:
        event: The Lambda event payload

    Returns:
        True if this is an EventBridge event, False otherwise
    """
    # EventBridge events have a 'source' field and 'detail-type'
    # API Gateway events have 'requestContext' with 'http' or 'requestId'
    return "source" in event and "detail-type" in event and "detail" in event


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Multi-purpose Lambda handler for API Gateway and EventBridge events.

    Routes incoming events to the appropriate handler:
    - EventBridge events -> MenuEventHandler
    - API Gateway requests -> FastAPI via Mangum

    Args:
        event: The Lambda event payload (EventBridge or API Gateway)
        context: The Lambda context object

    Returns:
        Response dict with statusCode and body
    """
    # Log incoming event for debugging (be careful with PII in production)
    logger.info(f"Received Lambda invocation, request_id: {context.request_id}")
    logger.debug(f"Event type check - has source: {'source' in event}")

    try:
        # Route based on event type
        if is_eventbridge_event(event):
            logger.info(
                f"Processing EventBridge event: {event.get('source')} - {event.get('detail-type')}"
            )
            return handle_eventbridge_event(event)
        else:
            logger.info("Processing API Gateway request via Mangum")
            result: dict[str, Any] = mangum_handler(event, context)
            return result

    except Exception as e:
        logger.exception(f"Unhandled error in Lambda handler: {e}")
        return {
            "statusCode": 500,
            "body": f"Internal server error: {str(e)}",
        }


def handle_eventbridge_event(event: dict[str, Any]) -> dict[str, Any]:
    """Handle EventBridge menu change events.

    Args:
        event: The EventBridge event payload

    Returns:
        Response dict with statusCode and body
    """
    try:
        # Extract event source and type
        source = event.get("source", "")
        detail_type = event.get("detail-type", "")

        logger.info(f"EventBridge event - Source: {source}, Type: {detail_type}")

        # Validate this is a menu changed event
        if source != "com.restaurant.menu" or detail_type != "MenuChanged":
            logger.warning(f"Unsupported event type: {source}/{detail_type}")
            return {
                "statusCode": 400,
                "body": f"Unsupported event type: {source}/{detail_type}",
            }

        # Parse the event detail
        detail = event.get("detail", {})
        menu_event = MenuChangedEvent(
            restaurant_id=detail.get("restaurant_id", ""),
            event_type=detail.get("event_type", "menu.updated"),
            timestamp=detail.get("timestamp", ""),
        )

        # Get event handler and process
        event_handler = get_event_handler()

        # Run async handler in event loop
        success = asyncio.run(event_handler.handle_menu_changed(menu_event))

        if success:
            logger.info(
                f"Successfully processed menu change for restaurant {menu_event.restaurant_id}"
            )
            return {
                "statusCode": 200,
                "body": f"Successfully processed menu change for restaurant {menu_event.restaurant_id}",
            }
        else:
            logger.error(f"Failed to sync menu for restaurant {menu_event.restaurant_id}")
            return {
                "statusCode": 500,
                "body": f"Failed to sync menu for restaurant {menu_event.restaurant_id}",
            }

    except Exception as e:
        logger.exception(f"Error processing EventBridge event: {e}")
        return {
            "statusCode": 500,
            "body": f"Error processing event: {str(e)}",
        }
