"""OpenTelemetry configuration and setup."""

import logging
import os
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)


def get_service_resource() -> Resource:
    """Create OpenTelemetry resource with service identification.

    Returns:
        Resource with service name and environment attributes
    """
    service_name = os.getenv("OTEL_SERVICE_NAME", "sync-svc")
    environment = os.getenv("ENVIRONMENT", "development")

    return Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
        }
    )


def setup_tracing(resource: Resource) -> None:
    """Configure OpenTelemetry tracing.

    Args:
        resource: Service resource for trace identification
    """
    # Create OTLP exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")

    # Create tracer provider with batch processor
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    logger.info(f"OpenTelemetry tracing configured with endpoint: {otlp_endpoint}")


def setup_metrics(resource: Resource) -> None:
    """Configure OpenTelemetry metrics.

    Args:
        resource: Service resource for metric identification
    """
    # Create OTLP metric exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics")

    # Create meter provider with periodic reader
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
    provider = MeterProvider(resource=resource, metric_readers=[reader])

    # Set as global meter provider
    metrics.set_meter_provider(provider)

    logger.info(f"OpenTelemetry metrics configured with endpoint: {otlp_endpoint}")


def setup_auto_instrumentation() -> None:
    """Configure automatic instrumentation for FastAPI, httpx, and boto3."""
    # Instrument httpx for platform API calls
    HTTPXClientInstrumentor().instrument()

    # Instrument boto3 for DynamoDB operations
    Boto3SQSInstrumentor().instrument()

    logger.info("Auto-instrumentation enabled for httpx and boto3")


def setup_observability(app: Any = None, enable_exporters: bool = True) -> None:
    """Initialize OpenTelemetry with tracing, metrics, and auto-instrumentation.

    Args:
        app: Optional FastAPI application to instrument
        enable_exporters: Whether to enable OTLP exporters (default: True, set False for tests)
    """
    # Check if we're in test environment
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "test":
        enable_exporters = False

    # Create service resource
    resource = get_service_resource()

    # Only setup exporters if enabled (skip in test environments)
    if enable_exporters:
        # Setup tracing
        setup_tracing(resource)

        # Setup metrics
        setup_metrics(resource)
    else:
        # Setup minimal tracing and metrics without exporters for testing
        TracerProvider(resource=resource)
        trace.set_tracer_provider(TracerProvider(resource=resource))

        MeterProvider(resource=resource)
        metrics.set_meter_provider(MeterProvider(resource=resource))

    # Setup auto-instrumentation
    setup_auto_instrumentation()

    # Instrument FastAPI if provided
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI application instrumented")

    logger.info("OpenTelemetry observability fully configured")


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured JSON logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Get log level from environment or use provided default
    level_str = os.getenv("LOG_LEVEL", log_level).upper()
    level = getattr(logging, level_str, logging.INFO)

    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        timestamp=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger.info(f"Structured JSON logging configured at {level_str} level")
