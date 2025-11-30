"""Unit tests for sync repository classes."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from restaurant_sync_service.models.sync_models import (
    SyncError,
    SyncOperation,
    SyncStatus,
    SyncStatusEnum,
)
from restaurant_sync_service.repositories.sync_repositories import (
    SyncErrorRepository,
    SyncOperationRepository,
    SyncStatusRepository,
)


@pytest.mark.unit
class TestSyncStatusRepository:
    """Test suite for SyncStatusRepository."""

    @pytest.fixture
    def mock_dynamodb(self) -> MagicMock:
        """Create a mock DynamoDB resource."""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_dynamodb: MagicMock) -> SyncStatusRepository:
        """Create a SyncStatusRepository with mocked DynamoDB."""
        return SyncStatusRepository(dynamodb_resource=mock_dynamodb, table_name="test-sync-status")

    def test_repository_initialization(self, mock_dynamodb: MagicMock) -> None:
        """Test that repository initializes correctly."""
        repo = SyncStatusRepository(dynamodb_resource=mock_dynamodb, table_name="test-table")
        assert repo.table_name == "test-table"
        mock_dynamodb.Table.assert_called_once_with("test-table")

    def test_get_status_success(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully retrieving sync status."""
        now = datetime.now(UTC)
        mock_dynamodb.Table.return_value.get_item.return_value = {
            "Item": {
                "restaurant_id": "rest_123",
                "platform": "doordash",
                "status": "completed",
                "last_sync_time": now.isoformat(),
                "item_count": 42,
            }
        }

        status = repository.get_status("rest_123", "doordash")

        assert status is not None
        assert status.restaurant_id == "rest_123"
        assert status.platform == "doordash"
        assert status.status == SyncStatusEnum.COMPLETED
        assert status.item_count == 42

    def test_get_status_not_found(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test retrieving non-existent sync status returns None."""
        mock_dynamodb.Table.return_value.get_item.return_value = {}

        status = repository.get_status("rest_123", "doordash")

        assert status is None

    def test_get_status_dynamodb_error(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that DynamoDB errors return None."""
        mock_dynamodb.Table.return_value.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "GetItem"
        )

        status = repository.get_status("rest_123", "doordash")

        assert status is None

    def test_save_status_success(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully saving sync status."""
        status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
        )

        result = repository.save_status(status)

        assert result is True
        mock_dynamodb.Table.return_value.put_item.assert_called_once()

    def test_save_status_dynamodb_error(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that save returns False on DynamoDB error."""
        mock_dynamodb.Table.return_value.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "PutItem"
        )

        status = SyncStatus(
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.COMPLETED,
        )

        result = repository.save_status(status)

        assert result is False

    def test_list_statuses_for_restaurant(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test listing all sync statuses for a restaurant."""
        mock_dynamodb.Table.return_value.query.return_value = {
            "Items": [
                {
                    "restaurant_id": "rest_123",
                    "platform": "doordash",
                    "status": "completed",
                },
                {
                    "restaurant_id": "rest_123",
                    "platform": "ubereats",
                    "status": "pending",
                },
            ]
        }

        statuses = repository.list_statuses_for_restaurant("rest_123")

        assert len(statuses) == 2
        assert statuses[0].platform == "doordash"
        assert statuses[1].platform == "ubereats"

    def test_list_statuses_for_restaurant_empty(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test listing statuses when none exist."""
        mock_dynamodb.Table.return_value.query.return_value = {"Items": []}

        statuses = repository.list_statuses_for_restaurant("rest_123")

        assert len(statuses) == 0

    def test_delete_status_success(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully deleting sync status."""
        result = repository.delete_status("rest_123", "doordash")

        assert result is True
        mock_dynamodb.Table.return_value.delete_item.assert_called_once()

    def test_delete_status_dynamodb_error(
        self, repository: SyncStatusRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that delete returns False on DynamoDB error."""
        mock_dynamodb.Table.return_value.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "DeleteItem"
        )

        result = repository.delete_status("rest_123", "doordash")

        assert result is False


@pytest.mark.unit
class TestSyncErrorRepository:
    """Test suite for SyncErrorRepository."""

    @pytest.fixture
    def mock_dynamodb(self) -> MagicMock:
        """Create a mock DynamoDB resource."""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_dynamodb: MagicMock) -> SyncErrorRepository:
        """Create a SyncErrorRepository with mocked DynamoDB."""
        return SyncErrorRepository(dynamodb_resource=mock_dynamodb, table_name="test-sync-errors")

    def test_repository_initialization(self, mock_dynamodb: MagicMock) -> None:
        """Test that repository initializes correctly."""
        repo = SyncErrorRepository(dynamodb_resource=mock_dynamodb, table_name="test-table")
        assert repo.table_name == "test-table"

    def test_save_error_success(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully saving sync error."""
        now = datetime.now(UTC)
        error = SyncError(
            error_id="err_123",
            created_at=now,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Auth failed",
        )

        result = repository.save_error(error)

        assert result is True
        mock_dynamodb.Table.return_value.put_item.assert_called_once()

    def test_save_error_dynamodb_error(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that save returns False on DynamoDB error."""
        mock_dynamodb.Table.return_value.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "PutItem"
        )

        now = datetime.now(UTC)
        error = SyncError(
            error_id="err_123",
            created_at=now,
            restaurant_id="rest_123",
            platform="doordash",
            error_details="Auth failed",
        )

        result = repository.save_error(error)

        assert result is False

    def test_get_error_success(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully retrieving sync error."""
        now = datetime.now(UTC)
        mock_dynamodb.Table.return_value.get_item.return_value = {
            "Item": {
                "error_id": "err_123",
                "created_at": now.isoformat(),
                "restaurant_id": "rest_123",
                "platform": "doordash",
                "error_details": "Auth failed",
                "retry_count": 2,
            }
        }

        error = repository.get_error("err_123", now)

        assert error is not None
        assert error.error_id == "err_123"
        assert error.platform == "doordash"
        assert error.retry_count == 2

    def test_get_error_not_found(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test retrieving non-existent error returns None."""
        mock_dynamodb.Table.return_value.get_item.return_value = {}

        error = repository.get_error("err_123", datetime.now(UTC))

        assert error is None

    def test_list_errors_for_restaurant(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test listing errors for a restaurant."""
        now = datetime.now(UTC)
        mock_dynamodb.Table.return_value.query.return_value = {
            "Items": [
                {
                    "error_id": "err_1",
                    "created_at": now.isoformat(),
                    "restaurant_id": "rest_123",
                    "platform": "doordash",
                    "error_details": "Error 1",
                    "retry_count": 0,
                },
                {
                    "error_id": "err_2",
                    "created_at": now.isoformat(),
                    "restaurant_id": "rest_123",
                    "platform": "doordash",
                    "error_details": "Error 2",
                    "retry_count": 1,
                },
            ]
        }

        errors = repository.list_errors_for_restaurant("rest_123", limit=10)

        assert len(errors) == 2
        assert errors[0].error_id == "err_1"
        assert errors[1].error_id == "err_2"

    def test_update_retry_count_success(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully updating retry count."""
        now = datetime.now(UTC)

        result = repository.update_retry_count("err_123", now, 3)

        assert result is True
        mock_dynamodb.Table.return_value.update_item.assert_called_once()

    def test_update_retry_count_dynamodb_error(
        self, repository: SyncErrorRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that update returns False on DynamoDB error."""
        mock_dynamodb.Table.return_value.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "UpdateItem"
        )

        result = repository.update_retry_count("err_123", datetime.now(UTC), 3)

        assert result is False


@pytest.mark.unit
class TestSyncOperationRepository:
    """Test suite for SyncOperationRepository."""

    @pytest.fixture
    def mock_dynamodb(self) -> MagicMock:
        """Create a mock DynamoDB resource."""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_dynamodb: MagicMock) -> SyncOperationRepository:
        """Create a SyncOperationRepository with mocked DynamoDB."""
        return SyncOperationRepository(
            dynamodb_resource=mock_dynamodb, table_name="test-sync-operations"
        )

    def test_repository_initialization(self, mock_dynamodb: MagicMock) -> None:
        """Test that repository initializes correctly."""
        repo = SyncOperationRepository(dynamodb_resource=mock_dynamodb, table_name="test-table")
        assert repo.table_name == "test-table"

    def test_save_operation_success(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully saving sync operation."""
        operation = SyncOperation(
            operation_id="op_123",
            restaurant_id="rest_123",
            platform="doordash",
            status=SyncStatusEnum.IN_PROGRESS,
            total_items=100,
            items_processed=42,
        )

        result = repository.save_operation(operation)

        assert result is True
        mock_dynamodb.Table.return_value.put_item.assert_called_once()

    def test_get_operation_success(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully retrieving sync operation."""
        mock_dynamodb.Table.return_value.get_item.return_value = {
            "Item": {
                "operation_id": "op_123",
                "restaurant_id": "rest_123",
                "platform": "doordash",
                "status": "in_progress",
                "total_items": 100,
                "items_processed": 42,
            }
        }

        operation = repository.get_operation("op_123")

        assert operation is not None
        assert operation.operation_id == "op_123"
        assert operation.status == SyncStatusEnum.IN_PROGRESS
        assert operation.items_processed == 42

    def test_get_operation_not_found(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test retrieving non-existent operation returns None."""
        mock_dynamodb.Table.return_value.get_item.return_value = {}

        operation = repository.get_operation("op_123")

        assert operation is None

    def test_update_progress_success(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully updating operation progress."""
        result = repository.update_progress("op_123", 75)

        assert result is True
        mock_dynamodb.Table.return_value.update_item.assert_called_once()

    def test_update_progress_dynamodb_error(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test that update returns False on DynamoDB error."""
        mock_dynamodb.Table.return_value.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "UpdateItem"
        )

        result = repository.update_progress("op_123", 75)

        assert result is False

    def test_update_status_success(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully updating operation status."""
        result = repository.update_status("op_123", SyncStatusEnum.COMPLETED)

        assert result is True
        mock_dynamodb.Table.return_value.update_item.assert_called_once()

    def test_delete_operation_success(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test successfully deleting sync operation."""
        result = repository.delete_operation("op_123")

        assert result is True
        mock_dynamodb.Table.return_value.delete_item.assert_called_once()

    def test_list_operations_for_restaurant(
        self, repository: SyncOperationRepository, mock_dynamodb: MagicMock
    ) -> None:
        """Test listing operations for a restaurant."""
        mock_dynamodb.Table.return_value.query.return_value = {
            "Items": [
                {
                    "operation_id": "op_1",
                    "restaurant_id": "rest_123",
                    "platform": "doordash",
                    "status": "in_progress",
                    "total_items": 100,
                    "items_processed": 50,
                },
                {
                    "operation_id": "op_2",
                    "restaurant_id": "rest_123",
                    "platform": "ubereats",
                    "status": "completed",
                    "total_items": 75,
                    "items_processed": 75,
                },
            ]
        }

        operations = repository.list_operations_for_restaurant("rest_123")

        assert len(operations) == 2
        assert operations[0].operation_id == "op_1"
        assert operations[1].operation_id == "op_2"
