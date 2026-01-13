"""Shared dependency factory for Lambda handlers.

This module provides cached dependency initialization to optimize Lambda cold starts.
Dependencies are created once and reused across invocations within the same Lambda container.
"""

import logging
import os
from typing import Any

import boto3
from fastapi import FastAPI

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.adapters.doordash_adapter import DoorDashAdapter
from restaurant_sync_service.handlers.api_handler import create_app
from restaurant_sync_service.handlers.event_handler import MenuEventHandler
from restaurant_sync_service.observability import configure_logging
from restaurant_sync_service.repositories.sync_repositories import (
    SyncErrorRepository,
    SyncStatusRepository,
)
from restaurant_sync_service.services.error_service import ErrorService
from restaurant_sync_service.services.menu_service_client import MenuServiceClient
from restaurant_sync_service.services.sync_service import SyncService

logger = logging.getLogger(__name__)

# Module-level caches for Lambda container reuse
_dynamodb_resource: Any | None = None
_platform_adapters: dict[str, PlatformAdapter] | None = None
_sync_service: SyncService | None = None
_error_service: ErrorService | None = None
_event_handler: MenuEventHandler | None = None
_fastapi_app: FastAPI | None = None


def get_dynamodb_resource() -> Any:
    """Create or retrieve cached DynamoDB resource.

    Returns:
        Boto3 DynamoDB resource configured for environment
    """
    global _dynamodb_resource

    if _dynamodb_resource is not None:
        return _dynamodb_resource

    endpoint_url = os.getenv("DYNAMODB_ENDPOINT")
    region = os.getenv("AWS_REGION", "us-east-1")

    if endpoint_url:
        # Local DynamoDB - use environment variables
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        logger.info(f"Using local DynamoDB at {endpoint_url}")
        _dynamodb_resource = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    else:
        logger.info(f"Using AWS DynamoDB in region {region}")
        _dynamodb_resource = boto3.resource("dynamodb", region_name=region)

    return _dynamodb_resource


def get_platform_adapters() -> dict[str, PlatformAdapter]:
    """Create or retrieve cached platform adapters.

    Returns:
        Dictionary mapping platform names to their configured adapters
    """
    global _platform_adapters

    if _platform_adapters is not None:
        return _platform_adapters

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
    # TODO: Add Grubhub adapter when implemented

    if not adapters:
        logger.warning("No platform adapters configured")

    _platform_adapters = adapters
    return _platform_adapters


def get_sync_service() -> SyncService:
    """Create or retrieve cached sync service.

    Returns:
        Configured SyncService instance
    """
    global _sync_service

    if _sync_service is not None:
        return _sync_service

    # Get DynamoDB resource
    dynamodb_resource = get_dynamodb_resource()

    # Create repositories
    status_table = os.getenv("DYNAMODB_SYNC_STATUS_TABLE", "restaurant-sync-status")
    status_repository = SyncStatusRepository(
        dynamodb_resource=dynamodb_resource, table_name=status_table
    )

    # Create menu service client
    menu_service_url = os.getenv("MENU_SERVICE_BASE_URL")
    menu_service_api_key = os.getenv("MENU_SERVICE_API_KEY")

    if not menu_service_url or not menu_service_api_key:
        raise ValueError(
            "MENU_SERVICE_BASE_URL and MENU_SERVICE_API_KEY must be set in environment"
        )

    menu_service_client = MenuServiceClient(base_url=menu_service_url, api_key=menu_service_api_key)

    # Create sync service
    retry_delay = int(os.getenv("RETRY_DELAY_SECONDS", "2"))
    _sync_service = SyncService(
        menu_service_client=menu_service_client,
        status_repository=status_repository,
        retry_delay_seconds=retry_delay,
    )

    logger.info("Sync service initialized")
    return _sync_service


def get_error_service() -> ErrorService:
    """Create or retrieve cached error service.

    Returns:
        Configured ErrorService instance
    """
    global _error_service

    if _error_service is not None:
        return _error_service

    # Get DynamoDB resource
    dynamodb_resource = get_dynamodb_resource()

    # Create error repository
    errors_table = os.getenv("DYNAMODB_SYNC_ERRORS_TABLE", "restaurant-sync-errors")
    error_repository = SyncErrorRepository(
        dynamodb_resource=dynamodb_resource, table_name=errors_table
    )

    _error_service = ErrorService(error_repository=error_repository)

    logger.info("Error service initialized")
    return _error_service


def get_event_handler() -> MenuEventHandler:
    """Create or retrieve cached event handler.

    Returns:
        Configured MenuEventHandler instance
    """
    global _event_handler

    if _event_handler is not None:
        return _event_handler

    sync_service = get_sync_service()
    error_service = get_error_service()
    platform_adapters = get_platform_adapters()

    _event_handler = MenuEventHandler(
        sync_service=sync_service,
        error_service=error_service,
        platform_adapters=platform_adapters,
    )

    logger.info("Event handler initialized")
    return _event_handler


def get_fastapi_app() -> FastAPI:
    """Create or retrieve cached FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    global _fastapi_app

    if _fastapi_app is not None:
        return _fastapi_app

    sync_service = get_sync_service()
    error_service = get_error_service()
    platform_adapters = get_platform_adapters()

    # Get API keys for admin endpoints
    api_keys_str = os.getenv("ADMIN_API_KEY", "")
    api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]

    if not api_keys:
        logger.warning("No ADMIN_API_KEY configured - using development key")
        api_keys = ["dummy-key-for-development"]

    _fastapi_app = create_app(
        sync_service=sync_service,
        error_service=error_service,
        platform_adapters=platform_adapters,
        api_keys=api_keys,
    )

    logger.info("FastAPI application initialized")
    return _fastapi_app


def initialize_lambda_environment() -> None:
    """Initialize Lambda environment with logging and observability.

    Should be called once during Lambda cold start.
    """
    # Configure structured logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(log_level)

    logger.info("Lambda environment initialized")
