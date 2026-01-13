"""Unit tests for main application entry point."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI

from src.main import create_application, create_platform_adapters, get_dynamodb_resource


@pytest.mark.unit
class TestGetDynamoDBResource:
    """Tests for get_dynamodb_resource function."""

    @patch.dict(os.environ, {"DYNAMODB_ENDPOINT": "", "AWS_REGION": "us-west-2"}, clear=True)
    @patch("src.main.boto3.resource")
    def test_creates_aws_resource_when_no_endpoint(self, mock_boto3_resource: Mock) -> None:
        """Test that AWS DynamoDB resource is created when no local endpoint configured."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with("dynamodb", region_name="us-west-2")
        assert result == mock_resource

    @patch.dict(
        os.environ,
        {"DYNAMODB_ENDPOINT": "http://localhost:8000", "AWS_REGION": "us-east-1"},
        clear=True,
    )
    @patch("src.main.boto3.resource")
    def test_creates_local_resource_when_endpoint_provided(self, mock_boto3_resource: Mock) -> None:
        """Test that local DynamoDB resource is created when endpoint configured."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )
        assert result == mock_resource

    @patch.dict(os.environ, {"DYNAMODB_ENDPOINT": ""}, clear=True)
    @patch("src.main.boto3.resource")
    def test_uses_default_region_when_not_specified(self, mock_boto3_resource: Mock) -> None:
        """Test that default region us-east-1 is used when AWS_REGION not set."""
        mock_resource = MagicMock()
        mock_boto3_resource.return_value = mock_resource

        result = get_dynamodb_resource()

        mock_boto3_resource.assert_called_once_with("dynamodb", region_name="us-east-1")
        assert result == mock_resource


@pytest.mark.unit
class TestCreatePlatformAdapters:
    """Tests for create_platform_adapters function."""

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
        adapters = create_platform_adapters()

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
        adapters = create_platform_adapters()

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
        adapters = create_platform_adapters()

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
        adapters = create_platform_adapters()

        assert "doordash" in adapters

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_empty_dict_when_no_adapters_configured(self) -> None:
        """Test that empty dict is returned when no platform adapters configured."""
        adapters = create_platform_adapters()

        assert adapters == {}
        assert len(adapters) == 0

    @patch.dict(
        os.environ,
        {
            "ENABLE_DOORDASH_SYNC": "true",
            "DOORDASH_CLIENT_ID": "test-client-id",
            "DOORDASH_CLIENT_SECRET": "test-client-secret",
            "DOORDASH_ENVIRONMENT": "production",
        },
        clear=True,
    )
    def test_respects_doordash_environment_setting(self) -> None:
        """Test that DoorDash adapter respects environment setting."""
        adapters = create_platform_adapters()

        assert "doordash" in adapters
        # Note: We can't directly test the environment param without exposing it,
        # but we verify the adapter was created


@pytest.mark.unit
class TestCreateApplication:
    """Tests for create_application function."""

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch("src.main.SyncStatusRepository")
    @patch("src.main.SyncErrorRepository")
    @patch("src.main.MenuServiceClient")
    @patch("src.main.SyncService")
    @patch("src.main.ErrorService")
    @patch("src.main.create_platform_adapters")
    @patch("src.main.create_app")
    @patch.dict(
        os.environ,
        {
            "LOG_LEVEL": "DEBUG",
            "DYNAMODB_SYNC_STATUS_TABLE": "test-status-table",
            "DYNAMODB_SYNC_ERRORS_TABLE": "test-errors-table",
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-menu-api-key",
            "RETRY_DELAY_SECONDS": "5",
            "ADMIN_API_KEY": "test-admin-key-1,test-admin-key-2",
        },
        clear=True,
    )
    def test_creates_application_with_all_dependencies(
        self,
        mock_create_app: Mock,
        mock_create_adapters: Mock,
        mock_error_service: Mock,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_error_repo: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that application is created with all dependencies properly wired."""
        # Setup mocks
        mock_dynamodb = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb

        mock_status_repository = MagicMock()
        mock_status_repo.return_value = mock_status_repository

        mock_error_repository = MagicMock()
        mock_error_repo.return_value = mock_error_repository

        mock_menu_service_client = MagicMock()
        mock_menu_client.return_value = mock_menu_service_client

        mock_sync_svc = MagicMock()
        mock_sync_service.return_value = mock_sync_svc

        mock_error_svc = MagicMock()
        mock_error_service.return_value = mock_error_svc

        mock_adapters = {"doordash": MagicMock()}
        mock_create_adapters.return_value = mock_adapters

        mock_app = MagicMock(spec=FastAPI)
        mock_create_app.return_value = mock_app

        # Execute
        result = create_application()

        # Verify logging configured
        mock_configure_logging.assert_called_once_with("DEBUG")

        # Verify DynamoDB resource created
        mock_get_dynamodb.assert_called_once()

        # Verify repositories created
        mock_status_repo.assert_called_once_with(
            dynamodb_resource=mock_dynamodb, table_name="test-status-table"
        )
        mock_error_repo.assert_called_once_with(
            dynamodb_resource=mock_dynamodb, table_name="test-errors-table"
        )

        # Verify menu service client created
        mock_menu_client.assert_called_once_with(
            base_url="https://menu-service.example.com", api_key="test-menu-api-key"
        )

        # Verify sync service created
        mock_sync_service.assert_called_once_with(
            menu_service_client=mock_menu_service_client,
            status_repository=mock_status_repository,
            retry_delay_seconds=5,
        )

        # Verify error service created
        mock_error_service.assert_called_once_with(error_repository=mock_error_repository)

        # Verify platform adapters created
        mock_create_adapters.assert_called_once()

        # Verify FastAPI app created with correct dependencies
        mock_create_app.assert_called_once_with(
            sync_service=mock_sync_svc,
            error_service=mock_error_svc,
            platform_adapters=mock_adapters,
            api_keys=["test-admin-key-1", "test-admin-key-2"],
        )

        # Verify correct app returned
        assert result == mock_app

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "",
            "MENU_SERVICE_API_KEY": "test-key",
        },
        clear=True,
    )
    def test_raises_error_when_menu_service_url_missing(
        self,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that ValueError is raised when MENU_SERVICE_BASE_URL not set."""
        mock_get_dynamodb.return_value = MagicMock()

        with pytest.raises(
            ValueError, match="MENU_SERVICE_BASE_URL and MENU_SERVICE_API_KEY must be set"
        ):
            create_application()

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "",
        },
        clear=True,
    )
    def test_raises_error_when_menu_service_api_key_missing(
        self,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that ValueError is raised when MENU_SERVICE_API_KEY not set."""
        mock_get_dynamodb.return_value = MagicMock()

        with pytest.raises(
            ValueError, match="MENU_SERVICE_BASE_URL and MENU_SERVICE_API_KEY must be set"
        ):
            create_application()

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch("src.main.SyncStatusRepository")
    @patch("src.main.SyncErrorRepository")
    @patch("src.main.MenuServiceClient")
    @patch("src.main.SyncService")
    @patch("src.main.ErrorService")
    @patch("src.main.create_platform_adapters")
    @patch("src.main.create_app")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-menu-api-key",
            "ADMIN_API_KEY": "",
        },
        clear=True,
    )
    def test_uses_dummy_key_when_no_admin_api_key_configured(
        self,
        mock_create_app: Mock,
        mock_create_adapters: Mock,
        mock_error_service: Mock,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_error_repo: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that dummy API key is used when ADMIN_API_KEY not set."""
        # Setup mocks
        mock_get_dynamodb.return_value = MagicMock()
        mock_status_repo.return_value = MagicMock()
        mock_error_repo.return_value = MagicMock()
        mock_menu_client.return_value = MagicMock()
        mock_sync_service.return_value = MagicMock()
        mock_error_service.return_value = MagicMock()
        mock_create_adapters.return_value = {}
        mock_create_app.return_value = MagicMock(spec=FastAPI)

        # Execute
        create_application()

        # Verify dummy key was used
        call_args = mock_create_app.call_args
        assert call_args is not None
        assert call_args.kwargs["api_keys"] == ["dummy-key-for-development"]

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch("src.main.SyncStatusRepository")
    @patch("src.main.SyncErrorRepository")
    @patch("src.main.MenuServiceClient")
    @patch("src.main.SyncService")
    @patch("src.main.ErrorService")
    @patch("src.main.create_platform_adapters")
    @patch("src.main.create_app")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-menu-api-key",
            "RETRY_DELAY_SECONDS": "10",
        },
        clear=True,
    )
    def test_uses_custom_retry_delay_when_configured(
        self,
        mock_create_app: Mock,
        mock_create_adapters: Mock,
        mock_error_service: Mock,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_error_repo: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that custom retry delay is used when RETRY_DELAY_SECONDS set."""
        # Setup mocks
        mock_get_dynamodb.return_value = MagicMock()
        mock_status_repo.return_value = MagicMock()
        mock_error_repo.return_value = MagicMock()
        mock_menu_client.return_value = MagicMock()
        mock_error_service.return_value = MagicMock()
        mock_create_adapters.return_value = {}
        mock_create_app.return_value = MagicMock(spec=FastAPI)

        # Execute
        create_application()

        # Verify retry delay was used
        call_args = mock_sync_service.call_args
        assert call_args is not None
        assert call_args.kwargs["retry_delay_seconds"] == 10

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch("src.main.SyncStatusRepository")
    @patch("src.main.SyncErrorRepository")
    @patch("src.main.MenuServiceClient")
    @patch("src.main.SyncService")
    @patch("src.main.ErrorService")
    @patch("src.main.create_platform_adapters")
    @patch("src.main.create_app")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-menu-api-key",
        },
        clear=True,
    )
    def test_uses_default_retry_delay_when_not_configured(
        self,
        mock_create_app: Mock,
        mock_create_adapters: Mock,
        mock_error_service: Mock,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_error_repo: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that default retry delay of 2 seconds is used when not configured."""
        # Setup mocks
        mock_get_dynamodb.return_value = MagicMock()
        mock_status_repo.return_value = MagicMock()
        mock_error_repo.return_value = MagicMock()
        mock_menu_client.return_value = MagicMock()
        mock_error_service.return_value = MagicMock()
        mock_create_adapters.return_value = {}
        mock_create_app.return_value = MagicMock(spec=FastAPI)

        # Execute
        create_application()

        # Verify default retry delay was used
        call_args = mock_sync_service.call_args
        assert call_args is not None
        assert call_args.kwargs["retry_delay_seconds"] == 2

    @patch("src.main.configure_logging")
    @patch("src.main.get_dynamodb_resource")
    @patch("src.main.SyncStatusRepository")
    @patch("src.main.SyncErrorRepository")
    @patch("src.main.MenuServiceClient")
    @patch("src.main.SyncService")
    @patch("src.main.ErrorService")
    @patch("src.main.create_platform_adapters")
    @patch("src.main.create_app")
    @patch.dict(
        os.environ,
        {
            "MENU_SERVICE_BASE_URL": "https://menu-service.example.com",
            "MENU_SERVICE_API_KEY": "test-menu-api-key",
            "ADMIN_API_KEY": "key1, key2 ,  key3  ",
        },
        clear=True,
    )
    def test_strips_whitespace_from_api_keys(
        self,
        mock_create_app: Mock,
        mock_create_adapters: Mock,
        mock_error_service: Mock,
        mock_sync_service: Mock,
        mock_menu_client: Mock,
        mock_error_repo: Mock,
        mock_status_repo: Mock,
        mock_get_dynamodb: Mock,
        mock_configure_logging: Mock,
    ) -> None:
        """Test that whitespace is stripped from API keys in comma-separated list."""
        # Setup mocks
        mock_get_dynamodb.return_value = MagicMock()
        mock_status_repo.return_value = MagicMock()
        mock_error_repo.return_value = MagicMock()
        mock_menu_client.return_value = MagicMock()
        mock_sync_service.return_value = MagicMock()
        mock_error_service.return_value = MagicMock()
        mock_create_adapters.return_value = {}
        mock_create_app.return_value = MagicMock(spec=FastAPI)

        # Execute
        create_application()

        # Verify API keys were properly stripped
        call_args = mock_create_app.call_args
        assert call_args is not None
        assert call_args.kwargs["api_keys"] == ["key1", "key2", "key3"]
