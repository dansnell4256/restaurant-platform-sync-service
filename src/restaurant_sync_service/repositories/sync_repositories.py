"""DynamoDB repository classes for sync models.

These repositories provide CRUD operations for sync status, errors, and operations.
Following the pattern from the menu service, we use simple return values (None/False)
for expected failures rather than raising exceptions.
"""

import logging
from datetime import datetime

from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

from restaurant_sync_service.models.sync_models import (
    SyncError,
    SyncOperation,
    SyncStatus,
    SyncStatusEnum,
)

logger = logging.getLogger(__name__)


class SyncStatusRepository:
    """Repository for sync status CRUD operations.

    Manages sync status records in DynamoDB with composite key (restaurant_id, platform).
    """

    def __init__(self, dynamodb_resource: DynamoDBServiceResource, table_name: str) -> None:
        """Initialize repository.

        Args:
            dynamodb_resource: Boto3 DynamoDB resource
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = dynamodb_resource
        self.table_name = table_name
        self.table: Table = dynamodb_resource.Table(table_name)

    def get_status(self, restaurant_id: str, platform: str) -> SyncStatus | None:
        """Retrieve sync status for a restaurant-platform pair.

        Args:
            restaurant_id: Restaurant identifier
            platform: Platform name (e.g., 'doordash')

        Returns:
            SyncStatus if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={"restaurant_id": restaurant_id, "platform": platform}
            )

            if "Item" not in response:
                return None

            return SyncStatus.from_dynamodb_item(response["Item"])

        except ClientError as e:
            logger.error(f"Failed to get sync status: {e}")  # pragma: no cover
            return None

    def save_status(self, status: SyncStatus) -> bool:
        """Save or update sync status.

        Args:
            status: SyncStatus to save

        Returns:
            bool: True if save succeeded, False otherwise
        """
        try:
            self.table.put_item(Item=status.to_dynamodb_item())
            return True

        except ClientError as e:
            logger.error(f"Failed to save sync status: {e}")  # pragma: no cover
            return False

    def list_statuses_for_restaurant(self, restaurant_id: str) -> list[SyncStatus]:
        """List all sync statuses for a restaurant.

        Args:
            restaurant_id: Restaurant identifier

        Returns:
            list: List of SyncStatus objects (empty list if none found)
        """
        try:
            response = self.table.query(
                KeyConditionExpression="restaurant_id = :rid",
                ExpressionAttributeValues={":rid": restaurant_id},
            )

            return [SyncStatus.from_dynamodb_item(item) for item in response.get("Items", [])]

        except ClientError as e:
            logger.error(f"Failed to list sync statuses: {e}")  # pragma: no cover
            return []

    def delete_status(self, restaurant_id: str, platform: str) -> bool:
        """Delete sync status for a restaurant-platform pair.

        Args:
            restaurant_id: Restaurant identifier
            platform: Platform name

        Returns:
            bool: True if delete succeeded, False otherwise
        """
        try:
            self.table.delete_item(Key={"restaurant_id": restaurant_id, "platform": platform})
            return True

        except ClientError as e:
            logger.error(f"Failed to delete sync status: {e}")  # pragma: no cover
            return False


class SyncErrorRepository:
    """Repository for sync error CRUD operations.

    Manages sync error records in DynamoDB with composite key (error_id, created_at).
    """

    def __init__(self, dynamodb_resource: DynamoDBServiceResource, table_name: str) -> None:
        """Initialize repository.

        Args:
            dynamodb_resource: Boto3 DynamoDB resource
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = dynamodb_resource
        self.table_name = table_name
        self.table: Table = dynamodb_resource.Table(table_name)

    def save_error(self, error: SyncError) -> bool:
        """Save sync error.

        Args:
            error: SyncError to save

        Returns:
            bool: True if save succeeded, False otherwise
        """
        try:
            self.table.put_item(Item=error.to_dynamodb_item())
            return True

        except ClientError as e:
            logger.error(f"Failed to save sync error: {e}")  # pragma: no cover
            return False

    def get_error(self, error_id: str, created_at: datetime) -> SyncError | None:
        """Retrieve sync error by ID and creation timestamp.

        Args:
            error_id: Error identifier
            created_at: Error creation timestamp

        Returns:
            SyncError if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={"error_id": error_id, "created_at": created_at.isoformat()}
            )

            if "Item" not in response:
                return None

            return SyncError.from_dynamodb_item(response["Item"])

        except ClientError as e:
            logger.error(f"Failed to get sync error: {e}")  # pragma: no cover
            return None

    def list_errors_for_restaurant(self, restaurant_id: str, limit: int = 50) -> list[SyncError]:
        """List recent errors for a restaurant.

        Uses a Global Secondary Index on restaurant_id.

        Args:
            restaurant_id: Restaurant identifier
            limit: Maximum number of errors to return

        Returns:
            list: List of SyncError objects (empty list if none found)
        """
        try:
            response = self.table.query(
                IndexName="restaurant_id-index",
                KeyConditionExpression="restaurant_id = :rid",
                ExpressionAttributeValues={":rid": restaurant_id},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )

            return [SyncError.from_dynamodb_item(item) for item in response.get("Items", [])]

        except ClientError as e:
            logger.error(f"Failed to list sync errors: {e}")  # pragma: no cover
            return []

    def update_retry_count(self, error_id: str, created_at: datetime, retry_count: int) -> bool:
        """Update retry count for an error.

        Args:
            error_id: Error identifier
            created_at: Error creation timestamp
            retry_count: New retry count

        Returns:
            bool: True if update succeeded, False otherwise
        """
        try:
            self.table.update_item(
                Key={"error_id": error_id, "created_at": created_at.isoformat()},
                UpdateExpression="SET retry_count = :count",
                ExpressionAttributeValues={":count": retry_count},
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to update retry count: {e}")  # pragma: no cover
            return False


class SyncOperationRepository:
    """Repository for sync operation CRUD operations.

    Manages sync operation records in DynamoDB with operation_id as partition key.
    """

    def __init__(self, dynamodb_resource: DynamoDBServiceResource, table_name: str) -> None:
        """Initialize repository.

        Args:
            dynamodb_resource: Boto3 DynamoDB resource
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = dynamodb_resource
        self.table_name = table_name
        self.table: Table = dynamodb_resource.Table(table_name)

    def save_operation(self, operation: SyncOperation) -> bool:
        """Save or update sync operation.

        Args:
            operation: SyncOperation to save

        Returns:
            bool: True if save succeeded, False otherwise
        """
        try:
            self.table.put_item(Item=operation.to_dynamodb_item())
            return True

        except ClientError as e:
            logger.error(f"Failed to save sync operation: {e}")  # pragma: no cover
            return False

    def get_operation(self, operation_id: str) -> SyncOperation | None:
        """Retrieve sync operation by ID.

        Args:
            operation_id: Operation identifier

        Returns:
            SyncOperation if found, None otherwise
        """
        try:
            response = self.table.get_item(Key={"operation_id": operation_id})

            if "Item" not in response:
                return None

            return SyncOperation.from_dynamodb_item(response["Item"])

        except ClientError as e:
            logger.error(f"Failed to get sync operation: {e}")  # pragma: no cover
            return None

    def update_progress(self, operation_id: str, items_processed: int) -> bool:
        """Update progress for an operation.

        Args:
            operation_id: Operation identifier
            items_processed: Number of items processed

        Returns:
            bool: True if update succeeded, False otherwise
        """
        try:
            self.table.update_item(
                Key={"operation_id": operation_id},
                UpdateExpression="SET items_processed = :count",
                ExpressionAttributeValues={":count": items_processed},
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to update operation progress: {e}")  # pragma: no cover
            return False

    def update_status(self, operation_id: str, status: SyncStatusEnum) -> bool:
        """Update status for an operation.

        Args:
            operation_id: Operation identifier
            status: New status

        Returns:
            bool: True if update succeeded, False otherwise
        """
        try:
            self.table.update_item(
                Key={"operation_id": operation_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": status.value},
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to update operation status: {e}")  # pragma: no cover
            return False

    def delete_operation(self, operation_id: str) -> bool:
        """Delete sync operation.

        Args:
            operation_id: Operation identifier

        Returns:
            bool: True if delete succeeded, False otherwise
        """
        try:
            self.table.delete_item(Key={"operation_id": operation_id})
            return True

        except ClientError as e:
            logger.error(f"Failed to delete sync operation: {e}")  # pragma: no cover
            return False

    def list_operations_for_restaurant(self, restaurant_id: str) -> list[SyncOperation]:
        """List all operations for a restaurant.

        Uses a Global Secondary Index on restaurant_id.

        Args:
            restaurant_id: Restaurant identifier

        Returns:
            list: List of SyncOperation objects (empty list if none found)
        """
        try:
            response = self.table.query(
                IndexName="restaurant_id-index",
                KeyConditionExpression="restaurant_id = :rid",
                ExpressionAttributeValues={":rid": restaurant_id},
            )

            return [SyncOperation.from_dynamodb_item(item) for item in response.get("Items", [])]

        except ClientError as e:
            logger.error(f"Failed to list sync operations: {e}")  # pragma: no cover
            return []
