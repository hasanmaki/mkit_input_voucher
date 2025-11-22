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
    """Measure request execution time, safe even on exceptions."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            request.state.duration_ms = duration
            raise
        else:
            duration = (time.perf_counter() - start) * 1000
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
        if forwarded := request.headers.get("x-forwarded-for"):
            return forwarded.split(",")[0].strip()

        if real := request.headers.get("x-real-ip"):
            return real

        return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log AFTER all other middlewares enrich request.state."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            status = response.status_code if response else "error"

            logger.bind(
                trace_id=getattr(request.state, "trace_id", None),
                duration_ms=getattr(request.state, "duration_ms", None),
                client_ip=getattr(request.state, "client_ip", None),
                user_agent=getattr(request.state, "user_agent", None),
                status=status,
                method=request.method,
                path=request.url.path,
            ).info(
                f"{request.method} {request.url.path} | "
                f"status={status} | "
                f"{getattr(request.state, 'duration_ms', 0):.2f}ms"
            )
