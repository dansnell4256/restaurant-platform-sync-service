"""Unit tests for FastAPI admin endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from restaurant_sync_service.adapters.base_adapter import PlatformAdapter
from restaurant_sync_service.handlers.api_handler import create_app
from restaurant_sync_service.models.sync_models import SyncError, SyncStatus, SyncStatusEnum
from restaurant_sync_service.services.error_service import ErrorService
from restaurant_sync_service.services.sync_service import SyncResult, SyncService


@pytest.mark.unit
class TestHealthEndpoint:
    """Test suite for health check endpoint."""

    def test_health_check(self) -> None:
        """Test health check endpoint returns 200."""
        mock_sync_service = MagicMock(spec=SyncService)
        mock_error_service = MagicMock(spec=ErrorService)
        mock_adapters = {}

        app = create_app(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
            api_keys=["test-key"],
        )
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


@pytest.mark.unit
class TestSyncStatusEndpoints:
    """Test suite for sync status endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        mock_sync_service = MagicMock(spec=SyncService)
        mock_error_service = MagicMock(spec=ErrorService)
        mock_adapters: dict[str, PlatformAdapter] = {}

        app = create_app(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
            api_keys=["test-api-key"],
        )
        return TestClient(app)

    def test_get_sync_status_success(self, client: TestClient) -> None:
        """Test getting sync status for a restaurant."""
        mock_statuses = [
            SyncStatus(
                restaurant_id="rest_123",
                platform="doordash",
                status=SyncStatusEnum.COMPLETED,
                last_sync_time=datetime.now(UTC),
                item_count=42,
                external_menu_id="ext_123",
            )
        ]

        # Access the app's sync_service via app.state
        client.app.state.sync_service.get_all_statuses_for_restaurant = AsyncMock(
            return_value=mock_statuses
        )

        response = client.get("/admin/sync-status/rest_123", headers={"X-API-Key": "test-api-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["restaurant_id"] == "rest_123"
        assert data[0]["platform"] == "doordash"
        assert data[0]["status"] == "completed"  # Pydantic serializes enum as lowercase

    def test_get_sync_status_unauthorized(self, client: TestClient) -> None:
        """Test getting sync status without API key."""
        response = client.get("/admin/sync-status/rest_123")

        assert response.status_code == 401

    def test_get_sync_status_invalid_key(self, client: TestClient) -> None:
        """Test getting sync status with invalid API key."""
        response = client.get("/admin/sync-status/rest_123", headers={"X-API-Key": "invalid-key"})

        assert response.status_code == 401

    def test_get_sync_status_empty(self, client: TestClient) -> None:
        """Test getting sync status when none exists."""
        client.app.state.sync_service.get_all_statuses_for_restaurant = AsyncMock(return_value=[])

        response = client.get("/admin/sync-status/rest_123", headers={"X-API-Key": "test-api-key"})

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.unit
class TestManualSyncEndpoints:
    """Test suite for manual sync trigger endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        mock_sync_service = MagicMock(spec=SyncService)
        mock_error_service = MagicMock(spec=ErrorService)

        # Create mock adapters
        adapter1 = MagicMock(spec=PlatformAdapter)
        adapter2 = MagicMock(spec=PlatformAdapter)
        mock_adapters = {
            "doordash": adapter1,
            "ubereats": adapter2,
        }

        app = create_app(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
            api_keys=["test-api-key"],
        )
        return TestClient(app)

    def test_trigger_full_refresh_success(self, client: TestClient) -> None:
        """Test triggering a full menu refresh."""
        client.app.state.sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
                SyncResult(success=True, platform="ubereats", item_count=10),
            ]
        )

        response = client.post(
            "/admin/sync/rest_123/full-refresh", headers={"X-API-Key": "test-api-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["restaurant_id"] == "rest_123"
        assert data["success"] is True
        assert len(data["results"]) == 2

    def test_trigger_full_refresh_partial_failure(self, client: TestClient) -> None:
        """Test triggering refresh with partial failures."""
        client.app.state.sync_service.sync_to_multiple_platforms = AsyncMock(
            return_value=[
                SyncResult(success=True, platform="doordash", item_count=10),
                SyncResult(
                    success=False,
                    platform="ubereats",
                    item_count=0,
                    error_message="Failed",
                ),
            ]
        )
        client.app.state.error_service.record_sync_error = AsyncMock(return_value="err_123")

        response = client.post(
            "/admin/sync/rest_123/full-refresh", headers={"X-API-Key": "test-api-key"}
        )

        assert response.status_code == 207  # Multi-Status
        data = response.json()
        assert data["success"] is False
        assert len(data["results"]) == 2

    def test_trigger_platform_sync_success(self, client: TestClient) -> None:
        """Test triggering sync to a specific platform."""
        adapter = MagicMock(spec=PlatformAdapter)
        client.app.state.platform_adapters["doordash"] = adapter

        client.app.state.sync_service.sync_to_platform = AsyncMock(
            return_value=SyncResult(success=True, platform="doordash", item_count=10)
        )

        response = client.post(
            "/admin/sync/rest_123/platform/doordash",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["platform"] == "doordash"

    def test_trigger_platform_sync_invalid_platform(self, client: TestClient) -> None:
        """Test triggering sync to an invalid platform."""
        response = client.post(
            "/admin/sync/rest_123/platform/invalid",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 404
        assert "not configured" in response.json()["detail"]

    def test_trigger_platform_sync_failure(self, client: TestClient) -> None:
        """Test triggering platform sync that fails."""
        adapter = MagicMock(spec=PlatformAdapter)
        client.app.state.platform_adapters["doordash"] = adapter

        client.app.state.sync_service.sync_to_platform = AsyncMock(
            return_value=SyncResult(
                success=False, platform="doordash", item_count=0, error_message="Failed"
            )
        )
        client.app.state.error_service.record_sync_error = AsyncMock(return_value="err_123")

        response = client.post(
            "/admin/sync/rest_123/platform/doordash",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 500
        # HTTPException wraps the detail in a "detail" key
        data = response.json()
        assert "detail" in data
        error_detail = data["detail"]
        assert error_detail["success"] is False


@pytest.mark.unit
class TestErrorEndpoints:
    """Test suite for error management endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        mock_sync_service = MagicMock(spec=SyncService)
        mock_error_service = MagicMock(spec=ErrorService)
        mock_adapters: dict[str, PlatformAdapter] = {}

        app = create_app(
            sync_service=mock_sync_service,
            error_service=mock_error_service,
            platform_adapters=mock_adapters,
            api_keys=["test-api-key"],
        )
        return TestClient(app)

    def test_get_errors_for_restaurant(self, client: TestClient) -> None:
        """Test getting errors for a specific restaurant."""
        mock_errors = [
            SyncError(
                error_id="err_1",
                created_at=datetime.now(UTC),
                restaurant_id="rest_123",
                platform="doordash",
                error_details="Test error",
                menu_snapshot=None,
                retry_count=0,
            )
        ]

        client.app.state.error_service.get_errors_for_restaurant = AsyncMock(
            return_value=mock_errors
        )

        response = client.get("/admin/errors/rest_123", headers={"X-API-Key": "test-api-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["error_id"] == "err_1"
        assert data[0]["restaurant_id"] == "rest_123"

    def test_retry_error_success(self, client: TestClient) -> None:
        """Test retrying a failed sync."""
        # Mock error retrieval
        mock_error = SyncError(
            error_id="err_123",
            created_at=datetime.now(UTC),
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Previous failure",
            menu_snapshot=None,
            retry_count=0,
        )
        # Mock getting errors to find the one to retry
        client.app.state.error_service.get_errors_for_restaurant = AsyncMock(
            return_value=[mock_error]
        )

        # Mock platform adapter
        adapter = MagicMock(spec=PlatformAdapter)
        client.app.state.platform_adapters["doordash"] = adapter

        # Mock successful retry
        client.app.state.sync_service.sync_to_platform = AsyncMock(
            return_value=SyncResult(success=True, platform="doordash", item_count=10)
        )
        client.app.state.error_service.increment_retry_count = AsyncMock(return_value=True)

        response = client.post("/admin/errors/err_123/retry", headers={"X-API-Key": "test-api-key"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_retry_error_not_found(self, client: TestClient) -> None:
        """Test retrying a non-existent error."""
        client.app.state.error_service.get_errors_for_restaurant = AsyncMock(return_value=[])

        response = client.post(
            "/admin/errors/err_nonexistent/retry", headers={"X-API-Key": "test-api-key"}
        )

        assert response.status_code == 404
