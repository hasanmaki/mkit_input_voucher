from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppExceptionsError(Exception):
    """Base class untuk error aplikasi yang terstruktur."""

    def __init__(
        self,
        message: str | None = "An application error occurred",
        status_code: int | None = 500,
        context: dict[str, Any] | Any | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message or "An application error occurred")

        # trace_id wajib ada
        self.trace_id = trace_id or str(uuid4())
        self.status_code = status_code or 500

        # Normalize context ke dict biar konsisten
        if isinstance(context, dict):
            self.context = context.copy()  # shallow sudah cukup
        elif context is None:
            self.context = {}
        else:
            self.context = {"detail": context}

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "status_code": self.status_code,
            "context": self.context,
            "trace_id": self.trace_id,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(status={self.status_code}, "
            f"msg='{self}', trace_id='{self.trace_id}')"
        )


async def app_exception_handler(
    request: Request, exc: AppExceptionsError
) -> JSONResponse:
    """App exception handler untuk AppExceptionsError."""
    # Ambil trace_id dari middleware
    trace_id = getattr(request.state, "trace_id", exc.trace_id)
    exc.trace_id = trace_id

    logger.bind(
        trace_id=trace_id,
        path=request.url.path,
        method=request.method,
        duration_ms=getattr(request.state, "duration_ms", None),
        client_ip=getattr(request.state, "client_ip", None),
        user_agent=getattr(request.state, "user_agent", None),
    ).error(f"{exc!r} | context={exc.context}")

    headers = {"X-Trace-ID": trace_id}
    if hasattr(request.state, "duration_ms"):
        headers["X-Process-Time"] = f"{request.state.duration_ms:.2f}ms"

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_dict()},
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D103
    trace_id = getattr(request.state, "trace_id", str(uuid4()))

    logger.bind(
        trace_id=trace_id,
        path=request.url.path,
        method=request.method,
        duration_ms=getattr(request.state, "duration_ms", None),
        client_ip=getattr(request.state, "client_ip", None),
        user_agent=getattr(request.state, "user_agent", None),
        exc_info=True,
    ).error(f"UNHANDLED ERROR: {exc}")

    headers = {"X-Trace-ID": trace_id}
    if hasattr(request.state, "duration_ms"):
        headers["X-Process-Time"] = f"{request.state.duration_ms:.2f}ms"

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": exc.__class__.__name__,
                "trace_id": trace_id,
            }
        },
        headers=headers,
    )
