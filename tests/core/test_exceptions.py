"""Tests for src.core.exceptions module.

Tests for AppExceptionsError, app_exception_handler, and unhandled_exception_handler.
Covers error serialization, trace_id handling, status codes, and header injection.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.exceptions import (
    AppExceptionsError,
    app_exception_handler,
    unhandled_exception_handler,
)
from starlette.requests import Request


@pytest.mark.unit
class TestAppExceptionsError:
    """Test AppExceptionsError exception class."""

    def test_init_with_defaults(self):
        """Test AppExceptionsError initializes with default values.

        Should create exception with default status_code (500) and
        auto-generated trace_id.
        """
        # Arrange & Act
        exc = AppExceptionsError()

        # Assert
        assert str(exc) == "An application error occurred"
        assert exc.status_code == 500
        assert exc.trace_id is not None
        assert len(exc.trace_id) > 0

    def test_init_with_custom_values(self):
        """Test AppExceptionsError with custom parameters.

        Should accept custom message, status_code, context, and trace_id.
        """
        # Arrange
        custom_trace = str(uuid4())
        custom_context = {"user_id": 123, "operation": "create"}

        # Act
        exc = AppExceptionsError(
            message="Custom error",
            status_code=400,
            context=custom_context,
            trace_id=custom_trace,
        )

        # Assert
        assert str(exc) == "Custom error"
        assert exc.status_code == 400
        assert exc.trace_id == custom_trace
        assert exc.context == custom_context

    def test_to_dict_serialization(self):
        """Test to_dict returns proper error dictionary.

        Should include message, status_code, context, and trace_id.
        """
        # Arrange
        exc = AppExceptionsError(
            message="Error occurred",
            status_code=422,
            context={"field": "email"},
        )

        # Act
        result = exc.to_dict()

        # Assert
        assert result["message"] == "Error occurred"
        assert result["status_code"] == 422
        assert result["context"] == {"field": "email"}
        assert result["trace_id"] == exc.trace_id

    def test_repr_format(self):
        """Test __repr__ format.

        Should include class name, status code, message, and trace_id.
        """
        # Arrange
        exc = AppExceptionsError(
            message="Test error",
            status_code=403,
        )

        # Act
        repr_str = repr(exc)

        # Assert
        assert "AppExceptionsError" in repr_str
        assert "status=403" in repr_str
        assert "msg='Test error'" in repr_str
        assert "trace_id=" in repr_str

    @pytest.mark.parametrize(
        "status_code",
        [400, 401, 403, 404, 409, 422, 500],
    )
    def test_various_status_codes(self, status_code):
        """Test AppExceptionsError with various HTTP status codes.

        Should correctly store and return different status codes.
        """
        # Arrange & Act
        exc = AppExceptionsError(status_code=status_code)

        # Assert
        assert exc.status_code == status_code


@pytest.mark.integration
class TestExceptionHandlersIntegration:
    """Integration tests for exception handlers with FastAPI."""

    def test_app_exception_handler_integration(self):
        """Test AppExceptionsError handler in FastAPI context.

        Should return proper JSON response with headers.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise AppExceptionsError(
                message="Test error",
                status_code=400,
                context={"reason": "test"},
            )

        app.add_exception_handler(AppExceptionsError, app_exception_handler)  # type: ignore

        # Act
        client = TestClient(app)
        response = client.get("/test")

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == "Test error"
        # Header names are lowercase in response
        assert "x-trace-id" in response.headers

    def test_unhandled_exception_handler_integration(self):
        """Test unhandled exception handler in FastAPI context.

        Should catch stdlib exceptions and return 500.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Unexpected error")

        app.add_exception_handler(AppExceptionsError, app_exception_handler)  # type: ignore
        app.add_exception_handler(Exception, unhandled_exception_handler)

        # Act
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == "Internal server error"
        assert data["error"]["type"] == "ValueError"
        assert "trace_id" in data["error"]
        assert "x-trace-id" in response.headers

    def test_app_exception_with_custom_status(self):
        """Test AppExceptionsError with custom status code.

        Should return correct status code in response.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise AppExceptionsError(
                message="Not found",
                status_code=404,
            )

        app.add_exception_handler(AppExceptionsError, app_exception_handler)  # type: ignore

        # Act
        client = TestClient(app)
        response = client.get("/test")

        # Assert
        assert response.status_code == 404

    def test_exception_handler_includes_trace_id(self):
        """Test exception handlers include trace_id header.

        Should always include X-Trace-ID in response.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise AppExceptionsError(message="Test")

        app.add_exception_handler(AppExceptionsError, app_exception_handler)  # type: ignore

        # Act
        client = TestClient(app)
        response = client.get("/test")

        # Assert
        assert "X-Trace-ID" in response.headers
        trace_id = response.headers["X-Trace-ID"]
        assert len(trace_id) > 0

    def test_app_exception_handler_with_timing(self):
        """Test app_exception_handler includes X-Process-Time when available.

        Should include X-Process-Time header when duration_ms in request state.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            # Simulate middleware setting duration
            request.state.duration_ms = 42.5
            raise AppExceptionsError(message="Error with timing")

        app.add_exception_handler(AppExceptionsError, app_exception_handler)  # type: ignore

        # Act
        client = TestClient(app)
        response = client.get("/test")

        # Assert
        assert response.status_code == 500
        assert "X-Process-Time" in response.headers
        assert response.headers["X-Process-Time"] == "42.50ms"

    def test_unhandled_exception_handler_with_timing(self):
        """Test unhandled_exception_handler includes X-Process-Time.

        Should include X-Process-Time header when duration_ms in request state.
        """
        # Arrange
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            # Simulate middleware setting duration
            request.state.duration_ms = 123.456
            raise RuntimeError("Unexpected error")

        app.add_exception_handler(Exception, unhandled_exception_handler)

        # Act
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Assert
        assert response.status_code == 500
        assert "X-Process-Time" in response.headers
        assert response.headers["X-Process-Time"] == "123.46ms"
