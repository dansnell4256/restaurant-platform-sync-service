"""Unit tests for Lambda dependency factory."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.lambda_dependencies import (
    get_dynamodb_resource,
    get_platform_adapters,
    get_sync_service,
    initialize_lambda_environment,
)


@pytest.mark.unit
class TestGetDynamoDBResource:
    """Tests for get_dynamodb_resource function."""

    def teardown_method(self) -> None:
        """Clear cached resources after each test."""
        import src.lambda_dependencies as deps

        deps._dynamodb_resource = None

    @patch.dict(os.environ, {"DYNAMODB_ENDPOINT": "", "AWS_REGION": "us-west-2"}, clear=True)
    @patch("src.lambda_dependencies.boto3.resource")
    def test_creates_aws_resource_when_no_endpoint(self, mock_boto3_resource: Mock) -> None:
        """Test that AWS DynamoDB resource is created when no local endpoint configured."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with("dynamodb", region_name="us-west-2")
        assert result == mock_resource

    @patch.dict(
        os.environ,
        {
            "DYNAMODB_ENDPOINT": "http://localhost:8000",
            "AWS_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
        },
        clear=True,
    )
    @patch("src.lambda_dependencies.boto3.resource")
    def test_creates_local_resource_when_endpoint_provided(self, mock_boto3_resource: Mock) -> None:
        """Test that local DynamoDB resource is created when endpoint configured."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )
        assert result == mock_resource

    @patch.dict(os.environ, {"DYNAMODB_ENDPOINT": ""}, clear=True)
    @patch("src.lambda_dependencies.boto3.resource")
    def test_uses_default_region_when_not_specified(self, mock_boto3_resource: Mock) -> None:
        """Test that default region us-east-1 is used when AWS_REGION not set."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with("dynamodb", region_name="us-east-1")
        assert result == mock_resource

    @patch.dict(os.environ, {"DYNAMODB_ENDPOINT": ""}, clear=True)
    @patch("src.lambda_dependencies.boto3.resource")
    def test_caches_resource_for_reuse(self, mock_boto3_resource: Mock) -> None:
        """Test that DynamoDB resource is cached and reused across calls."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result1 = get_dynamodb_resource()
        result2 = get_dynamodb_resource()

        # Should only be created once
        mock_boto3_resource.assert_called_once()
        assert result1 is result2


@pytest.mark.unit
class TestGetPlatformAdapters:
    """Tests for get_platform_adapters function."""

    def teardown_method(self) -> None:
        """Clear cached adapters after each test."""
        import src.lambda_dependencies as deps

        deps._platform_adapters = None

    @patch.dict(
        os.environ,
        {
            "ENABLE_DOORDASH_SYNC": "true",
            "DOORDASH_CLIENT_ID": "test-client-id",
            "DOORDASH_CLIENT_SECRET": "test-client-secret",
            "DOORDASH_ENVIRONMENT": "sandbox",
        },
        clear=True,
    )
    def test_creates_doordash_adapter_when_configured(self) -> None:
        """Test that DoorDash adapter is created when credentials provided."""
        adapters = get_platform_adapters()

        assert "doordash" in adapters
        assert adapters["doordash"] is not None

    @patch.dict(
        os.environ,
        {
            "ENABLE_DOORDASH_SYNC": "true",
            "DOORDASH_CLIENT_ID": "",
            "DOORDASH_CLIENT_SECRET": "",
        },
        clear=True,
    )
    def test_skips_doordash_when_credentials_missing(self) -> None:
        """Test that DoorDash adapter is skipped when credentials not configured."""
        adapters = get_platform_adapters()

        assert "doordash" not in adapters
        assert len(adapters) == 0

    @patch.dict(
        os.environ,
        {
            "ENABLE_DOORDASH_SYNC": "false",
            "DOORDASH_CLIENT_ID": "test-client-id",
            "DOORDASH_CLIENT_SECRET": "test-client-secret",
        },
        clear=True,
    )
    def test_skips_doordash_when_disabled(self) -> None:
        """Test that DoorDash adapter is not created when feature flag disabled."""
        adapters = get_platform_adapters()

        assert "doordash" not in adapters
        assert len(adapters) == 0

    @patch.dict(
        os.environ,
        {
            "DOORDASH_CLIENT_ID": "test-client-id",
            "DOORDASH_CLIENT_SECRET": "test-client-secret",
        },
        clear=True,
    )
    def test_doordash_enabled_by_default(self) -> None:
        """Test that DoorDash sync is enabled by default when ENABLE_DOORDASH_SYNC not set."""
        adapters = get_platform_adapters()

        assert "doordash" in adapters

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_empty_dict_when_no_adapters_configured(self) -> None:
        """Test that empty dict is returned when no platform adapters configured."""
        adapters = get_platform_adapters()

        assert adapters == {}
        assert len(adapters) == 0

    @patch.dict(
        os.environ,
        {
            "DOORDASH_CLIENT_ID": "test-client-id",
            "DOORDASH_CLIENT_SECRET": "test-client-secret",
        },
        clear=True,
    )
    def test_caches_adapters_for_reuse(self) -> None:
        """Test that platform adapters are cached and reused across calls."""
        adapters1 = get_platform_adapters()
        adapters2 = get_platform_adapters()

        assert adapters1 is adapters2


@pytest.mark.unit
class TestGetSyncService:
    """Tests for get_sync_service function."""

    def teardown_method(self) -> None:
        """Clear cached services after each test."""
        import src.lambda_dependencies as deps

        deps._sync_service = None
        deps._dynamodb_resource = None

    @patch("src.lambda_dependencies.get_dynamodb_resource")
    @patch("src.lambda_dependencies.SyncStatusRepository")
    @patch("src.lambda_dependencies.MenuServiceClient")
    @patch("src.lambda_dependencies.SyncService")
    @patch.dict(
        os.environ,
        {
            "DYNAMODB_SYNC_STATUS_TABLE": "test-status-table",
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-api-key",
            "RETRY_DELAY_SECONDS": "5",
        },
        clear=True,
    )
    def test_creates_sync_service_with_dependencies(
        self,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
    ) -> None:
        """Test that sync service is created with correct dependencies."""
        mock_dynamodb = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb

        mock_repository = MagicMock()
        mock_status_repo.return_value = mock_repository

        mock_client = MagicMock()
        mock_menu_client.return_value = mock_client

        mock_service = MagicMock()
        mock_sync_service.return_value = mock_service

        result = get_sync_service()

        mock_status_repo.assert_called_once_with(
            dynamodb_resource=mock_dynamodb, table_name="test-status-table"
        )
        mock_menu_client.assert_called_once_with(
            base_url="https://menu-service.example.com", api_key="test-api-key"
        )
        mock_sync_service.assert_called_once_with(
            menu_service_client=mock_client,
            status_repository=mock_repository,
            retry_delay_seconds=5,
        )
        assert result == mock_service

    @patch("src.lambda_dependencies.get_dynamodb_resource")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "",
            "MENU_SERVICE_API_KEY": "test-key",
        },
        clear=True,
    )
    def test_raises_error_when_menu_service_url_missing(self, mock_get_dynamodb: Mock) -> None:
        """Test that ValueError is raised when MENU_SERVICE_BASE_URL not set."""
        mock_get_dynamodb.return_value = MagicMock()

        with pytest.raises(
            ValueError, match="MENU_SERVICE_BASE_URL and MENU_SERVICE_API_KEY must be set"
        ):
            get_sync_service()


@pytest.mark.unit
class TestInitializeLambdaEnvironment:
    """Tests for initialize_lambda_environment function."""

    @patch("src.lambda_dependencies.configure_logging")
    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True)
    def test_configures_logging_with_env_level(self, mock_configure_logging: Mock) -> None:
        """Test that logging is configured with LOG_LEVEL from environment."""
        initialize_lambda_environment()

        mock_configure_logging.assert_called_once_with("DEBUG")

    @patch("src.lambda_dependencies.configure_logging")
    @patch.dict(os.environ, {}, clear=True)
    def test_uses_default_log_level_when_not_set(self, mock_configure_logging: Mock) -> None:
        """Test that default INFO level is used when LOG_LEVEL not set."""
        initialize_lambda_environment()

        mock_configure_logging.assert_called_once_with("INFO")
