import time
from collections.abc import Callable
from uuid import uuid4

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject unique trace ID for every incoming request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = str(uuid4())
        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Measure request execution time."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000  # ms

        request.state.duration_ms = duration
        response.headers["X-Process-Time"] = f"{duration:.2f}ms"

        return response


class ClientInfoMiddleware(BaseHTTPMiddleware):
    """Capture client IP and user-agent."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.client_ip = self._get_ip(request)
        request.state.user_agent = request.headers.get("user-agent", "unknown")
        return await call_next(request)

    @staticmethod
    def _get_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log the request AFTER all other middlewares fill request.state."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        logger.bind(
            trace_id=getattr(request.state, "trace_id", None),
            duration_ms=getattr(request.state, "duration_ms", None),
            client_ip=getattr(request.state, "client_ip", None),
            user_agent=getattr(request.state, "user_agent", None),
            status=response.status_code,
            method=request.method,
            path=request.url.path,
        ).info(
            f"{request.method} {request.url.path} | "
            f"status={response.status_code} | "
            f"{getattr(request.state, 'duration_ms', 0):.2f}ms"
        )

        return response
