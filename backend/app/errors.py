"""Typed application errors + exception handlers.

Error bodies conform to the frozen ``ErrorResponse`` contract schema
(code/message/detail/request_id/errors) and are served with the
``application/problem+json`` media type plus an ``X-Request-ID`` header.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging import get_logger, get_request_id
from app.schemas import ErrorResponse, FieldError

_PROBLEM_JSON = "application/problem+json"
_log = get_logger("marsgis.errors")


class AppError(Exception):
    """Base class for every expected (non-500) application error."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationErrorApp(AppError):
    status_code = 422
    code = "validation_error"

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        errors: list[FieldError] | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.errors = errors or []


class QuotaExceededError(AppError):
    status_code = 429
    code = "quota_exceeded"


class EngineError(AppError):
    status_code = 502
    code = "engine_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


def _envelope(
    status_code: int,
    code: str,
    message: str,
    detail: str | None = None,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        detail=detail,
        request_id=get_request_id(),
        errors=errors or None,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        media_type=_PROBLEM_JSON,
        headers={"X-Request-ID": get_request_id() or ""},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        errors = getattr(exc, "errors", None)
        if exc.status_code >= 500:
            _log.error("app_error", code=exc.code, message=exc.message, detail=exc.detail)
        return _envelope(exc.status_code, exc.code, exc.message, exc.detail, errors)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors: list[FieldError] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
            field_errors.append(FieldError(field=loc or "body", message=err.get("msg", "invalid")))
        return _envelope(422, "validation_error", "Request validation failed", errors=field_errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            400: "bad_request",
            401: "unauthorized",
            404: "not_found",
            405: "method_not_allowed",
        }.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code
        return _envelope(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        _log.exception("unhandled_exception", error=str(exc))
        return _envelope(500, "internal_error", "Internal server error")
