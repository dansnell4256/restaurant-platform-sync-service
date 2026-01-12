"""OpenTelemetry tracing decorators."""

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


def traced(span_name: str | None = None, service_name: str = "sync-svc") -> Callable[[F], F]:
    """Decorator to add OpenTelemetry tracing to a function.

    Creates a new span for the decorated function with automatic error tracking.
    Async functions are supported.

    Args:
        span_name: Name for the span (defaults to function name if not provided)
        service_name: Service name for span attributes

    Returns:
        Decorated function with tracing

    Example:
        @traced("sync_restaurant_menu", service_name="sync-svc")
        async def sync_to_platform(restaurant_id: str) -> bool:
            # Function implementation
            pass
    """

    def decorator(func: F) -> F:
        # Use provided span name or default to function name
        name = span_name or func.__name__

        # Get tracer for this service
        tracer = trace.get_tracer(service_name)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name) as span:
                # Add service name as span attribute
                span.set_attribute("service.name", service_name)

                # Add function name if using custom span name
                if span_name:
                    span.set_attribute("function.name", func.__name__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name) as span:
                # Add service name as span attribute
                span.set_attribute("service.name", service_name)

                # Add function name if using custom span name
                if span_name:
                    span.set_attribute("function.name", func.__name__)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
