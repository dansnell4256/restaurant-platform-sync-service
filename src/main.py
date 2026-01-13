"""Main application entry point for the restaurant sync service.

This module provides the FastAPI application entry point for running
the service locally with uvicorn or in production with a WSGI server.

For AWS Lambda deployment, use lambda_handler.py instead.
"""

import logging
import os

from fastapi import FastAPI

from lambda_dependencies import get_fastapi_app, initialize_lambda_environment

logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application with all dependencies.

    This factory function uses the shared lambda_dependencies module to
    create the application, ensuring consistency between local dev and
    Lambda deployment.

    Returns:
        Configured FastAPI application instance
    """
    # Initialize environment (logging, etc.)
    initialize_lambda_environment()

    logger.info("Initializing restaurant sync service...")

    # Get the FastAPI app from shared dependencies
    app = get_fastapi_app()

    logger.info("Restaurant sync service initialized successfully")

    return app


# Create the FastAPI application instance (only when not in test mode)
# This prevents the app from being created during test collection
# We use if-else instead of ternary to avoid calling create_application() before checking
if os.getenv("ENVIRONMENT") != "test":  # noqa: SIM108
    app = create_application()
else:
    # Create a placeholder app for test imports
    app = FastAPI()


if __name__ == "__main__":
    """Run the application with uvicorn when executed directly."""
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting development server on {host}:{port}")
    logger.info(f"API documentation available at http://{host}:{port}/docs")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
