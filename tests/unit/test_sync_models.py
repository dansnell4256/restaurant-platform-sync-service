"""Unit tests for sync status models."""

from datetime import UTC, datetime

import pytest

from restaurant_sync_service.models.sync_models import (
    SyncError,
    SyncOperation,
    SyncStatus,
    SyncStatusEnum,
)


@pytest.mark.unit
class TestSyncStatusEnum:
    """Test suite for SyncStatusEnum."""

    def test_all_status_values_are_defined(self) -> None:
        """Test that all expected status values are defined."""
        assert SyncStatusEnum.PENDING == "pending"
        assert SyncStatusEnum.IN_PROGRESS == "in_progress"
        assert SyncStatusEnum.COMPLETED == "completed"
        assert SyncStatusEnum.FAILED == "failed"


@pytest.mark.unit
class TestSyncStatus:
    """Test suite for SyncStatus model."""

    def test_sync_status_creation_with_required_fields(self) -> None:
        """Test creating sync status with only required fields."""
        status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.PENDING,
        )

        assert status.restaurant_id == "rest_123"
        assert status.platform == "doordash"
        assert status.status == SyncStatusEnum.PENDING
        assert status.last_sync_time is None
        assert status.item_count is None
        assert status.external_menu_id is None

    def test_sync_status_creation_with_all_fields(self) -> None:
        """Test creating sync status with all fields."""
        now = datetime.now(UTC)
        status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
            last_sync_time=now,
            item_count=42,
            external_menu_id="ext_menu_456",
        )

        assert status.restaurant_id == "rest_123"
        assert status.platform == "doordash"
        assert status.status == SyncStatusEnum.COMPLETED
        assert status.last_sync_time == now
        assert status.item_count == 42
        assert status.external_menu_id == "ext_menu_456"

    def test_sync_status_validates_item_count_non_negative(self) -> None:
        """Test that item_count must be non-negative."""
        with pytest.raises(ValueError):
            SyncStatus(
                restaurant_id="rest_123",
                platform="doordash",
                status=SyncStatusEnum.COMPLETED,
                item_count=-1,
            )

    def test_sync_status_converts_to_dynamodb_format(self) -> None:
        """Test converting sync status to DynamoDB item format."""
        now = datetime.now(UTC)
        status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
            last_sync_time=now,
            item_count=42,
            external_menu_id="ext_menu_456",
        )

        dynamodb_item = status.to_dynamodb_item()

        assert dynamodb_item["restaurant_id"] == "rest_123"
        assert dynamodb_item["platform"] == "doordash"
        assert dynamodb_item["status"] == "completed"
        assert dynamodb_item["last_sync_time"] == now.isoformat()
        assert dynamodb_item["item_count"] == 42
        assert dynamodb_item["external_menu_id"] == "ext_menu_456"

    def test_sync_status_creates_from_dynamodb_format(self) -> None:
        """Test creating sync status from DynamoDB item."""
        now = datetime.now(UTC)
        dynamodb_item = {
            "restaurant_id": "rest_123",
            "platform": "doordash",
            "status": "completed",
            "last_sync_time": now.isoformat(),
            "item_count": 42,
            "external_menu_id": "ext_menu_456",
        }

        status = SyncStatus.from_dynamodb_item(dynamodb_item)

        assert status.restaurant_id == "rest_123"
        assert status.platform == "doordash"
        assert status.status == SyncStatusEnum.COMPLETED
        assert status.last_sync_time == now
        assert status.item_count == 42
        assert status.external_menu_id == "ext_menu_456"


@pytest.mark.unit
class TestSyncError:
    """Test suite for SyncError model."""

    def test_sync_error_creation_with_required_fields(self) -> None:
        """Test creating sync error with only required fields."""
        now = datetime.now(UTC)
        error = SyncError(
            error_id="err_123",
            created_at=now,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Authentication failed",
        )

        assert error.error_id == "err_123"
        assert error.created_at == now
        assert error.restaurant_id == "rest_123"
        assert error.platform == "doordash"
        assert error.error_details == "Authentication failed"
        assert error.menu_snapshot is None
        assert error.retry_count == 0

    def test_sync_error_creation_with_all_fields(self) -> None:
        """Test creating sync error with all fields."""
        now = datetime.now(UTC)
        menu_snapshot = {"items": [{"id": "item_1", "name": "Burger"}]}
        error = SyncError(
            error_id="err_123",
            created_at=now,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Network timeout",
            menu_snapshot=menu_snapshot,
            retry_count=3,
        )

        assert error.error_id == "err_123"
        assert error.created_at == now
        assert error.restaurant_id == "rest_123"
        assert error.platform == "doordash"
        assert error.error_details == "Network timeout"
        assert error.menu_snapshot == menu_snapshot
        assert error.retry_count == 3

    def test_sync_error_validates_retry_count_non_negative(self) -> None:
        """Test that retry_count must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValueError):
            SyncError(
                error_id="err_123",
                created_at=now,
                restaurant_id="rest_123",
                platform="doordash",
                error_details="Error",
                retry_count=-1,
            )

    def test_sync_error_converts_to_dynamodb_format(self) -> None:
        """Test converting sync error to DynamoDB item format."""
        now = datetime.now(UTC)
        menu_snapshot = {"items": [{"id": "item_1"}]}
        error = SyncError(
            error_id="err_123",
            created_at=now,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Network timeout",
            menu_snapshot=menu_snapshot,
            retry_count=2,
        )

        dynamodb_item = error.to_dynamodb_item()

        assert dynamodb_item["error_id"] == "err_123"
        assert dynamodb_item["created_at"] == now.isoformat()
        assert dynamodb_item["restaurant_id"] == "rest_123"
        assert dynamodb_item["platform"] == "doordash"
        assert dynamodb_item["error_details"] == "Network timeout"
        assert dynamodb_item["menu_snapshot"] == menu_snapshot
        assert dynamodb_item["retry_count"] == 2

    def test_sync_error_creates_from_dynamodb_format(self) -> None:
        """Test creating sync error from DynamoDB item."""
        now = datetime.now(UTC)
        menu_snapshot = {"items": [{"id": "item_1"}]}
        dynamodb_item = {
            "error_id": "err_123",
            "created_at": now.isoformat(),
            "restaurant_id": "rest_123",
            "platform": "doordash",
            "error_details": "Network timeout",
            "menu_snapshot": menu_snapshot,
            "retry_count": 2,
        }

        error = SyncError.from_dynamodb_item(dynamodb_item)

        assert error.error_id == "err_123"
        assert error.created_at == now
        assert error.restaurant_id == "rest_123"
        assert error.platform == "doordash"
        assert error.error_details == "Network timeout"
        assert error.menu_snapshot == menu_snapshot
        assert error.retry_count == 2


@pytest.mark.unit
class TestSyncOperation:
    """Test suite for SyncOperation model."""

    def test_sync_operation_creation_with_required_fields(self) -> None:
        """Test creating sync operation with only required fields."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.PENDING,
            total_items=100,
        )

        assert operation.operation_id == "op_123"
        assert operation.restaurant_id == "rest_123"
        assert operation.platform == "doordash"
        assert operation.status == SyncStatusEnum.PENDING
        assert operation.total_items == 100
        assert operation.items_processed == 0

    def test_sync_operation_creation_with_all_fields(self) -> None:
        """Test creating sync operation with all fields."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.IN_PROGRESS,
            total_items=100,
            items_processed=42,
        )

        assert operation.operation_id == "op_123"
        assert operation.restaurant_id == "rest_123"
        assert operation.platform == "doordash"
        assert operation.status == SyncStatusEnum.IN_PROGRESS
        assert operation.total_items == 100
        assert operation.items_processed == 42

    def test_sync_operation_validates_total_items_positive(self) -> None:
        """Test that total_items must be positive."""
        with pytest.raises(ValueError):
            SyncOperation(
                operation_id="op_123",
                restaurant_id="rest_123",
                platform="doordash",
                status=SyncStatusEnum.PENDING,
                total_items=0,
            )

    def test_sync_operation_validates_items_processed_non_negative(self) -> None:
        """Test that items_processed must be non-negative."""
        with pytest.raises(ValueError):
            SyncOperation(
                operation_id="op_123",
                restaurant_id="rest_123",
                platform="doordash",
                status=SyncStatusEnum.PENDING,
                total_items=100,
                items_processed=-1,
            )

    def test_sync_operation_calculates_progress_percentage(self) -> None:
        """Test calculating progress percentage."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.IN_PROGRESS,
            total_items=100,
            items_processed=42,
        )

        assert operation.progress_percentage == 42.0

    def test_sync_operation_progress_percentage_zero_when_no_items_processed(self) -> None:
        """Test progress percentage is 0 when no items processed."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.PENDING,
            total_items=100,
            items_processed=0,
        )

        assert operation.progress_percentage == 0.0

    def test_sync_operation_progress_percentage_hundred_when_complete(self) -> None:
        """Test progress percentage is 100 when all items processed."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
            total_items=100,
            items_processed=100,
        )

        assert operation.progress_percentage == 100.0

    def test_sync_operation_converts_to_dynamodb_format(self) -> None:
        """Test converting sync operation to DynamoDB item format."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.IN_PROGRESS,
            total_items=100,
            items_processed=42,
        )

        dynamodb_item = operation.to_dynamodb_item()

        assert dynamodb_item["operation_id"] == "op_123"
        assert dynamodb_item["restaurant_id"] == "rest_123"
        assert dynamodb_item["platform"] == "doordash"
        assert dynamodb_item["status"] == "in_progress"
        assert dynamodb_item["total_items"] == 100
        assert dynamodb_item["items_processed"] == 42

    def test_sync_operation_creates_from_dynamodb_format(self) -> None:
        """Test creating sync operation from DynamoDB item."""
        dynamodb_item = {
            "operation_id": "op_123",
            "restaurant_id": "rest_123",
            "platform": "doordash",
            "status": "in_progress",
            "total_items": 100,
            "items_processed": 42,
        }

        operation = SyncOperation.from_dynamodb_item(dynamodb_item)

        assert operation.operation_id == "op_123"
        assert operation.restaurant_id == "rest_123"
        assert operation.platform == "doordash"
        assert operation.status == SyncStatusEnum.IN_PROGRESS
        assert operation.total_items == 100
        assert operation.items_processed == 42
