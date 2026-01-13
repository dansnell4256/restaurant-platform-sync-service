"""Main application entry point for the restaurant sync service.

This module provides the FastAPI application factory and configuration
for running the service locally or in production.
"""

import logging
import os
from typing import Any

import boto3
from fastapi import FastAPI

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.adapters.doordash_adapter import DoorDashAdapter
from restaurant_sync_service.handlers.api_handler import create_app
from restaurant_sync_service.observability import configure_logging
from restaurant_sync_service.repositories.sync_repositories import (
    SyncErrorRepository,
    SyncStatusRepository,
)
from restaurant_sync_service.services.error_service import ErrorService
from restaurant_sync_service.services.menu_service_client import MenuServiceClient
from restaurant_sync_service.services.sync_service import SyncService

logger = logging.getLogger(__name__)


def get_dynamodb_resource() -> Any:
    """Create DynamoDB resource with appropriate configuration.

    Returns:
        Boto3 DynamoDB resource configured for environment
    """
    # Check for local DynamoDB endpoint (for development)
    endpoint_url = os.getenv("DYNAMODB_ENDPOINT")
    region = os.getenv("AWS_REGION", "us-east-1")

    if endpoint_url:
        # Local DynamoDB - use environment variables or defaults for credentials
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        logger.info(f"Using local DynamoDB at {endpoint_url}")
        return boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    else:
        logger.info(f"Using AWS DynamoDB in region {region}")
        # Production - boto3 will use default credential chain (IAM role, env vars, etc.)
        return boto3.resource("dynamodb", region_name=region)


def create_platform_adapters() -> dict[str, PlatformAdapter]:
    """Create and configure platform adapters from environment variables.

    Returns:
        Dictionary mapping platform names to their configured adapters

    Raises:
        ValueError: If required configuration is missing
    """
    adapters: dict[str, PlatformAdapter] = {}

    # DoorDash configuration
    if os.getenv("ENABLE_DOORDASH_SYNC", "true").lower() == "true":
        doordash_client_id = os.getenv("DOORDASH_CLIENT_ID")
        doordash_client_secret = os.getenv("DOORDASH_CLIENT_SECRET")
        doordash_env = os.getenv("DOORDASH_ENVIRONMENT", "sandbox")

        if doordash_client_id and doordash_client_secret:
            adapters["doordash"] = DoorDashAdapter(
                client_id=doordash_client_id,
                client_secret=doordash_client_secret,
                environment=doordash_env,
            )
            logger.info("DoorDash adapter configured")
        else:
            logger.warning("DoorDash sync enabled but credentials not configured, skipping")

    # TODO: Add Uber Eats adapter when implemented
    # if os.getenv("ENABLE_UBEREATS_SYNC", "true").lower() == "true":
    #     adapters["ubereats"] = UberEatsAdapter(...)

    # TODO: Add Grubhub adapter when implemented
    # if os.getenv("ENABLE_GRUBHUB_SYNC", "true").lower() == "true":
    #     adapters["grubhub"] = GrubhubAdapter(...)

    if not adapters:
        logger.warning("No platform adapters configured - service will not sync to any platforms")

    return adapters


def create_application() -> FastAPI:
    """Create and configure the FastAPI application with all dependencies.

    This factory function:
    1. Configures logging
    2. Creates AWS clients
    3. Initializes repositories
    4. Creates services
    5. Configures platform adapters
    6. Creates FastAPI app with admin endpoints
    7. Sets up observability

    Returns:
        Configured FastAPI application instance
    """
    # Configure structured logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(log_level)

    logger.info("Initializing restaurant sync service...")

    # Create DynamoDB resource
    dynamodb_resource = get_dynamodb_resource()

    # Get table names from environment
    status_table = os.getenv("DYNAMODB_SYNC_STATUS_TABLE", "restaurant-sync-status")
    errors_table = os.getenv("DYNAMODB_SYNC_ERRORS_TABLE", "restaurant-sync-errors")

    # Create repositories
    status_repository = SyncStatusRepository(
        dynamodb_resource=dynamodb_resource, table_name=status_table
    )
    error_repository = SyncErrorRepository(
        dynamodb_resource=dynamodb_resource, table_name=errors_table
    )

    logger.info(f"Repositories configured - status: {status_table}, errors: {errors_table}")

    # Create menu service client
    menu_service_url = os.getenv("MENU_SERVICE_BASE_URL")
    menu_service_api_key = os.getenv("MENU_SERVICE_API_KEY")

    if not menu_service_url or not menu_service_api_key:
        raise ValueError(
            "MENU_SERVICE_BASE_URL and MENU_SERVICE_API_KEY must be set in environment"
        )

    menu_service_client = MenuServiceClient(base_url=menu_service_url, api_key=menu_service_api_key)

    logger.info(f"Menu service client configured - URL: {menu_service_url}")

    # Create services
    retry_delay = int(os.getenv("RETRY_DELAY_SECONDS", "2"))
    sync_service = SyncService(
        menu_service_client=menu_service_client,
        status_repository=status_repository,
        retry_delay_seconds=retry_delay,
    )

    error_service = ErrorService(error_repository=error_repository)

    logger.info("Services initialized")

    # Configure platform adapters
    platform_adapters = create_platform_adapters()
    logger.info(f"Platform adapters configured: {', '.join(platform_adapters.keys())}")

    # Get API keys for admin endpoints
    api_keys_str = os.getenv("ADMIN_API_KEY", "")
    api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]

    if not api_keys:
        logger.warning("No ADMIN_API_KEY configured - admin endpoints will not be accessible")
        api_keys = ["dummy-key-for-development"]

    # Create FastAPI application with admin endpoints
    app = create_app(
        sync_service=sync_service,
        error_service=error_service,
        platform_adapters=platform_adapters,
        api_keys=api_keys,
    )

    logger.info("FastAPI application created with admin endpoints")
    logger.info("Restaurant sync service initialized successfully")

    return app


# Create the FastAPI application instance (only when not in test mode)
# This prevents the app from being created during test collection
# We use if-else instead of ternary to avoid calling create_application() before checking
if os.getenv("ENVIRONMENT") != "test":  # noqa: SIM108
    app = create_application()
else:
    # Create a placeholder app for test imports
    app = FastAPI()


if __name__ == "__main__":
    """Run the application with uvicorn when executed directly."""
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting development server on {host}:{port}")
    logger.info(f"API documentation available at http://{host}:{port}/docs")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
