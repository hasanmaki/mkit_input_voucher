"""Fixtures for core module tests."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import Headers


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    return FastAPI()


@pytest.fixture
def client(app):
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_request():
    """Create a mock Request object with essential attributes."""
    request = MagicMock(spec=Request)

    # Create a simple state object that supports attribute access
    state = MagicMock()
    state.trace_id = None
    request.state = state

    request.url = MagicMock()
    request.url.path = "/test"
    request.method = "GET"
    request.headers = Headers({"user-agent": "test-agent"})
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_request_with_forwarded():
    """Create a mock Request with X-Forwarded-For header."""
    request = MagicMock(spec=Request)

    state = MagicMock()
    state.trace_id = None
    request.state = state

    request.url = MagicMock()
    request.url.path = "/test"
    request.method = "POST"
    request.headers = Headers({"x-forwarded-for": "192.168.1.100, 192.168.1.99"})
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_response():
    """Create a mock Response object."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    return response


@pytest.fixture
def async_middleware_call():
    """Factory for creating async middleware call_next functions."""

    def create_call_next(response_status: int = 200, should_raise: bool = False):
        async def call_next(request):  # noqa: ARG001
            if should_raise:
                raise ValueError("Test error")
            response = MagicMock()
            response.status_code = response_status
            response.headers = {}
            return response

        return call_next

    return create_call_next


@pytest.fixture(scope="function")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
