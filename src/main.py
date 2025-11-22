from collections.abc import Callable
from typing import cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from src.core.exceptions import (
    AppExceptionsError,
    app_exception_handler,
    unhandled_exception_handler,
)
from src.core.middlewares import (
    ClientInfoMiddleware,
    RequestLoggingMiddleware,
    RequestTimingMiddleware,
    TraceIDMiddleware,
)

app = FastAPI()

# Typing helper to satisfy static type checkers for exception handlers
ExceptionHandler = Callable[[Request, Exception], JSONResponse]

app.add_middleware(TraceIDMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(ClientInfoMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(
    AppExceptionsError, cast(ExceptionHandler, app_exception_handler)
)
app.add_exception_handler(
    Exception, cast(ExceptionHandler, unhandled_exception_handler)
)


@app.get("/health")
async def health_check():
    """Just a health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
