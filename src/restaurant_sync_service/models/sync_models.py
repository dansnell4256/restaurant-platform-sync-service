"""Sync status and error tracking models.

These models represent sync operations, status tracking, and error information
for DynamoDB storage and retrieval.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SyncStatusEnum(str, Enum):
    """Enumeration of sync status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncStatus(BaseModel):
    """Sync status tracking for restaurant-platform pairs.

    Represents the current sync status between a restaurant and a delivery platform.
    Stored in DynamoDB with (restaurant_id, platform) as composite key.
    """

    restaurant_id: str = Field(..., description="Restaurant identifier")
    platform: str = Field(..., description="Delivery platform name (e.g., 'doordash')")
    status: SyncStatusEnum = Field(..., description="Current sync status")
    last_sync_time: datetime | None = Field(None, description="Timestamp of last successful sync")
    item_count: int | None = Field(None, description="Number of items in last sync", ge=0)
    external_menu_id: str | None = Field(None, description="Platform-specific menu identifier")

    @field_validator("item_count")
    @classmethod
    def validate_item_count(cls, v: int | None) -> int | None:
        """Validate that item_count is non-negative."""
        if v is not None and v < 0:
            raise ValueError("item_count must be non-negative")
        return v

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format.

        Returns:
            dict: DynamoDB-compatible representation
        """
        item: dict[str, Any] = {
            "restaurant_id": self.restaurant_id,
            "platform": self.platform,
            "status": self.status.value,
        }

        if self.last_sync_time is not None:
            item["last_sync_time"] = self.last_sync_time.isoformat()

        if self.item_count is not None:
            item["item_count"] = self.item_count

        if self.external_menu_id is not None:
            item["external_menu_id"] = self.external_menu_id

        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "SyncStatus":
        """Create SyncStatus from DynamoDB item.

        Args:
            item: DynamoDB item dictionary

        Returns:
            SyncStatus: Parsed model instance
        """
        data: dict[str, Any] = {
            "restaurant_id": item["restaurant_id"],
            "platform": item["platform"],
            "status": SyncStatusEnum(item["status"]),
        }

        if "last_sync_time" in item:
            data["last_sync_time"] = datetime.fromisoformat(item["last_sync_time"])

        if "item_count" in item:
            data["item_count"] = item["item_count"]

        if "external_menu_id" in item:
            data["external_menu_id"] = item["external_menu_id"]

        return cls(**data)


class SyncError(BaseModel):
    """Sync error tracking for failed operations.

    Records detailed information about sync failures for debugging and retry logic.
    Stored in DynamoDB with (error_id, created_at) as composite key.
    """

    error_id: str = Field(..., description="Unique error identifier")
    created_at: datetime = Field(..., description="Error creation timestamp")
    restaurant_id: str = Field(..., description="Restaurant identifier")
    platform: str = Field(..., description="Delivery platform name")
    error_details: str = Field(..., description="Error message or details")
    menu_snapshot: dict[str, Any] | None = Field(
        None, description="Snapshot of menu data at time of error"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts", ge=0)

    @field_validator("retry_count")
    @classmethod
    def validate_retry_count(cls, v: int) -> int:
        """Validate that retry_count is non-negative."""
        if v < 0:
            raise ValueError("retry_count must be non-negative")
        return v

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format.

        Returns:
            dict: DynamoDB-compatible representation
        """
        item: dict[str, Any] = {
            "error_id": self.error_id,
            "created_at": self.created_at.isoformat(),
            "restaurant_id": self.restaurant_id,
            "platform": self.platform,
            "error_details": self.error_details,
            "retry_count": self.retry_count,
        }

        if self.menu_snapshot is not None:
            item["menu_snapshot"] = self.menu_snapshot

        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "SyncError":
        """Create SyncError from DynamoDB item.

        Args:
            item: DynamoDB item dictionary

        Returns:
            SyncError: Parsed model instance
        """
        data: dict[str, Any] = {
            "error_id": item["error_id"],
            "created_at": datetime.fromisoformat(item["created_at"]),
            "restaurant_id": item["restaurant_id"],
            "platform": item["platform"],
            "error_details": item["error_details"],
            "retry_count": item.get("retry_count", 0),
        }

        if "menu_snapshot" in item:
            data["menu_snapshot"] = item["menu_snapshot"]

        return cls(**data)


class SyncOperation(BaseModel):
    """Tracking for in-progress sync operations.

    Used to monitor long-running sync operations and report progress.
    Stored in DynamoDB with operation_id as partition key.
    """

    operation_id: str = Field(..., description="Unique operation identifier")
    restaurant_id: str = Field(..., description="Restaurant identifier")
    platform: str = Field(..., description="Delivery platform name")
    status: SyncStatusEnum = Field(..., description="Current operation status")
    total_items: int = Field(..., description="Total number of items to process", gt=0)
    items_processed: int = Field(default=0, description="Number of items processed so far", ge=0)

    @field_validator("total_items")
    @classmethod
    def validate_total_items(cls, v: int) -> int:
        """Validate that total_items is positive."""
        if v <= 0:
            raise ValueError("total_items must be positive")
        return v

    @field_validator("items_processed")
    @classmethod
    def validate_items_processed(cls, v: int) -> int:
        """Validate that items_processed is non-negative."""
        if v < 0:
            raise ValueError("items_processed must be non-negative")
        return v

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage.

        Returns:
            float: Progress percentage (0.0 to 100.0)
        """
        if self.total_items == 0:
            return 0.0
        return (self.items_processed / self.total_items) * 100.0

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format.

        Returns:
            dict: DynamoDB-compatible representation
        """
        return {
            "operation_id": self.operation_id,
            "restaurant_id": self.restaurant_id,
            "platform": self.platform,
            "status": self.status.value,
            "total_items": self.total_items,
            "items_processed": self.items_processed,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "SyncOperation":
        """Create SyncOperation from DynamoDB item.

        Args:
            item: DynamoDB item dictionary

        Returns:
            SyncOperation: Parsed model instance
        """
        return cls(
            operation_id=item["operation_id"],
            restaurant_id=item["restaurant_id"],
            platform=item["platform"],
            status=SyncStatusEnum(item["status"]),
            total_items=item["total_items"],
            items_processed=item.get("items_processed", 0),
        )
