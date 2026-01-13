"""Unit tests for main application entry point."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI

from src.main import create_application


@pytest.mark.unit
class TestCreateApplication:
    """Tests for create_application function."""

    @patch("src.main.initialize_lambda_environment")
    @patch("src.main.get_fastapi_app")
    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True)
    def test_creates_application_using_shared_dependencies(
        self,
        mock_get_app: Mock,
        mock_initialize: Mock,
    ) -> None:
        """Test that application is created using shared lambda dependencies."""
        mock_app = MagicMock(spec=FastAPI)
        mock_get_app.return_value = mock_app

        result = create_application()

        # Verify environment initialized
        mock_initialize.assert_called_once()

        # Verify app retrieved from shared dependencies
        mock_get_app.assert_called_once()

        # Verify correct app returned
        assert result == mock_app

    @patch("src.main.initialize_lambda_environment")
    @patch("src.main.get_fastapi_app")
    @patch.dict(os.environ, {}, clear=True)
    def test_works_with_default_environment(
        self,
        mock_get_app: Mock,
        mock_initialize: Mock,
    ) -> None:
        """Test that application works with default environment configuration."""
        mock_app = MagicMock(spec=FastAPI)
        mock_get_app.return_value = mock_app

        result = create_application()

        # Verify initialization and app creation succeeded
        mock_initialize.assert_called_once()
        mock_get_app.assert_called_once()
        assert result == mock_app
