"""Shared FastAPI dependencies."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_session as _get_session
from app.errors import UnauthorizedError


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in _get_session():
        yield session


def settings_dep() -> Settings:
    return get_settings()


def get_job_runner(request: Request):
    return request.app.state.job_runner


def _client_ip(request: Request) -> str:
    """Best-effort client IP for per-client quota/rate keys.

    X-Forwarded-For is client-controlled and trivially spoofable, so it is NOT
    trusted unless ``trust_forwarded_for`` is explicitly enabled (deployment is
    behind a trusted reverse proxy). The default relies on ``request.client``,
    which uvicorn populates from the real peer — correct when run with
    ``--proxy-headers`` behind the proxy. When trusting XFF we take the
    right-most hop (appended by the trusted proxy), not the left-most
    (contributed by the client).
    """
    if get_settings().trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                return hops[-1]
    return request.client.host if request.client else "unknown"


def client_fingerprint(request: Request) -> str:
    """Opaque per-client id: IP plus the API key (if any), hashed."""
    ip = _client_ip(request)
    api_key = request.headers.get("x-api-key", "")
    raw = f"{ip}|{api_key}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def require_api_key(request: Request) -> None:
    """No-op unless REQUIRE_API_KEY; then enforce a valid X-API-Key header."""
    settings = get_settings()
    if not settings.require_api_key:
        return
    provided = request.headers.get("x-api-key", "")
    if not provided or provided not in set(settings.api_keys):
        raise UnauthorizedError(
            "A valid X-API-Key header is required",
            detail="This deployment has REQUIRE_API_KEY=true.",
        )
