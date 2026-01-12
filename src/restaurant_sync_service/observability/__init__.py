"""OpenTelemetry instrumentation and observability utilities."""

from restaurant_sync_service.observability.config import configure_logging, setup_observability
from restaurant_sync_service.observability.decorators import traced

__all__ = ["setup_observability", "configure_logging", "traced"]
