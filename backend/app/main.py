"""App factory, lifespan, middleware, exception handlers, OpenAPI contract pin.

The lifespan runs schema migration + idempotent seeding and starts the job
runner; the runtime ``/openapi.json`` is pinned to the committed
``contracts/openapi.yaml`` so the frozen contract and the live API can never
drift (CI asserts equality).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.config import REPO_ROOT, get_settings
from app.errors import register_exception_handlers
from app.logging import configure_logging, get_logger, new_request_id, set_request_id
from app.schemas import ErrorResponse

_log = get_logger("marsgis.app")
_OPENAPI_PATH = REPO_ROOT / "contracts" / "openapi.yaml"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id, echo X-Request-ID, and emit a structured access log."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or new_request_id()
        set_request_id(rid)
        structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = rid
        return response


class MaxBodySizeMiddleware:
    """Reject oversized request bodies — pure-ASGI so the cap holds for BOTH a
    declared Content-Length AND the bytes actually received (a chunked request
    with no Content-Length cannot slip past). Bodies are buffered only up to the
    limit (small for this API), then replayed downstream."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self._max = max_bytes

    async def _reject(self, send) -> None:
        payload = ErrorResponse(
            code="payload_too_large",
            message="Request body too large",
            detail=f"Limit is {self._max} bytes.",
        ).model_dump(mode="json", exclude_none=True)
        data = json.dumps(payload).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(data)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": data})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        cl = headers.get(b"content-length")
        if cl is not None:
            try:
                if int(cl) > self._max:
                    await self._reject(send)
                    return
            except ValueError:
                pass

        body = bytearray()
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"") or b""
                more = message.get("more_body", False)
                if len(body) > self._max:
                    await self._reject(send)
                    return
            else:  # http.disconnect
                more = False

        buffered = bytes(body)
        sent = False

        async def _replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, _replay, send)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(json_logs=settings.json_logs, level=settings.log_level)

    from app.db.base import dispose_engine, init_engine
    from app.db.migrate import migrate
    from app.db.seed import seed
    from app.services.engine_adapter import build_engine_adapter
    from app.services.jobs.runner import build_runner

    init_engine(settings)
    await migrate(settings)
    if settings.seed_on_startup:
        await seed(settings)

    adapter = build_engine_adapter(settings)
    runner = build_runner(settings, adapter)
    await runner.start()
    app.state.engine_adapter = adapter
    app.state.job_runner = runner
    app.state.settings = settings
    _log.info(
        "startup.complete",
        job_backend=settings.job_backend,
        engine_mode=settings.engine_mode,
        require_api_key=settings.require_api_key,
    )

    try:
        yield
    finally:
        await runner.stop()
        await dispose_engine()
        _log.info("shutdown.complete")


_openapi_cache: dict[str, Any] | None = None


def _load_contract_openapi() -> dict[str, Any] | None:
    global _openapi_cache
    if _openapi_cache is not None:
        return _openapi_cache
    if not _OPENAPI_PATH.exists():
        _log.warning("openapi.contract_missing", path=str(_OPENAPI_PATH))
        return None
    import yaml

    with open(_OPENAPI_PATH, encoding="utf-8") as f:
        _openapi_cache = yaml.safe_load(f)
    return _openapi_cache


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(json_logs=settings.json_logs, level=settings.log_level)

    app = FastAPI(
        title="MarsGIS API",
        version="1.0.0",
        description="MarsGIS backend — Mars CRISM catalogue, SAM analysis jobs, result tiling.",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug or settings.app_env != "prod" else None,
        redoc_url=None,
    )

    # Middleware (outermost first): security headers -> request id -> body guard -> CORS.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Location"],
    )

    from app.api.router import api_router

    app.include_router(api_router, prefix="/api")
    register_exception_handlers(app)

    # Pin /openapi.json to the committed, frozen contract (CI asserts equality).
    def _custom_openapi() -> dict[str, Any]:
        contract = _load_contract_openapi()
        if contract is not None:
            app.openapi_schema = contract
            return contract
        from fastapi.openapi.utils import get_openapi

        app.openapi_schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        return app.openapi_schema

    app.openapi = _custom_openapi  # type: ignore[method-assign]

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": "MarsGIS API",
            "version": __version__,
            "contract_version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
