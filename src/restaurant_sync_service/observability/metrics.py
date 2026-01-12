"""Custom metrics for restaurant sync service."""

from opentelemetry import metrics

# Get meter for sync service
meter = metrics.get_meter("sync-svc")

# Menu sync success rate counter
sync_success_counter = meter.create_counter(
    name="menu_sync_success_total",
    description="Total number of successful menu syncs by platform",
    unit="1",
)

sync_failure_counter = meter.create_counter(
    name="menu_sync_failure_total",
    description="Total number of failed menu syncs by platform",
    unit="1",
)

# Menu sync duration histogram
sync_duration_histogram = meter.create_histogram(
    name="menu_sync_duration_seconds",
    description="Duration of menu sync operations by platform",
    unit="s",
)

# Error queue depth gauge
error_queue_depth = meter.create_up_down_counter(
    name="error_queue_depth",
    description="Current number of errors in the error queue",
    unit="1",
)

# Platform API response time histogram
platform_api_response_time = meter.create_histogram(
    name="platform_api_response_time_seconds",
    description="Response time for platform API calls",
    unit="s",
)


def record_sync_success(platform: str, item_count: int) -> None:  # noqa: ARG001
    """Record a successful menu sync.

    Args:
        platform: The platform that was synced (e.g., "doordash", "ubereats")
        item_count: Number of menu items synced
    """
    sync_success_counter.add(1, {"platform": platform})


def record_sync_failure(platform: str, error_type: str) -> None:
    """Record a failed menu sync.

    Args:
        platform: The platform that failed to sync
        error_type: Type of error that occurred
    """
    sync_failure_counter.add(1, {"platform": platform, "error_type": error_type})


def record_sync_duration(platform: str, duration_seconds: float) -> None:
    """Record the duration of a menu sync operation.

    Args:
        platform: The platform that was synced
        duration_seconds: Duration in seconds
    """
    sync_duration_histogram.record(duration_seconds, {"platform": platform})


def record_error_queue_change(change: int) -> None:
    """Record a change in the error queue depth.

    Args:
        change: Change in error count (positive for additions, negative for removals)
    """
    error_queue_depth.add(change)


def record_platform_api_call(platform: str, operation: str, duration_seconds: float) -> None:
    """Record a platform API call.

    Args:
        platform: The platform API that was called
        operation: The operation performed (e.g., "create_menu", "update_menu")
        duration_seconds: Duration in seconds
    """
    platform_api_response_time.record(
        duration_seconds, {"platform": platform, "operation": operation}
    )
