"""Health / readiness endpoint."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import Settings
from app.deps import get_session, settings_dep
from app.logging import get_logger
from app.schemas import HealthComponent, HealthComponents, HealthResponse
from app.schemas.enums import HealthStatus

router = APIRouter()
_log = get_logger("marsgis.health")


async def _db_component(session: AsyncSession) -> HealthComponent:
    start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000.0
        return HealthComponent(
            status=HealthStatus.ok, detail="reachable", latency_ms=round(latency, 2)
        )
    except Exception:  # pragma: no cover
        # Never leak driver/DSN internals to anonymous callers; log server-side.
        _log.warning("health.db_unreachable", exc_info=True)
        return HealthComponent(status=HealthStatus.down, detail="unreachable")


def _engine_component(request: Request) -> HealthComponent:
    adapter = getattr(request.app.state, "engine_adapter", None)
    if adapter is None:
        return HealthComponent(status=HealthStatus.down, detail="no adapter")
    version = adapter.version()
    if version in ("unavailable", "unknown"):
        return HealthComponent(status=HealthStatus.degraded, detail=f"engine {version}")
    return HealthComponent(status=HealthStatus.ok, detail=f"engine {version}")


def _tiler_component() -> HealthComponent:
    try:
        from app.core.tms import get_tms

        get_tms()
        return HealthComponent(status=HealthStatus.ok, detail="MarsEQC TMS ready")
    except Exception:  # pragma: no cover
        _log.warning("health.tiler_unavailable", exc_info=True)
        return HealthComponent(status=HealthStatus.degraded, detail="unavailable")


def _queue_component(request: Request, settings: Settings) -> HealthComponent:
    runner = getattr(request.app.state, "job_runner", None)
    if runner is None:
        return HealthComponent(status=HealthStatus.down, detail="no runner")
    st = runner.status()
    return HealthComponent(status=HealthStatus.ok, detail=f"{settings.job_backend}: {st}")


@router.get("/health", response_model=None)
async def get_health(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(settings_dep),
) -> HealthResponse:
    db = await _db_component(session)
    engine = _engine_component(request)
    tiler = _tiler_component()
    queue = _queue_component(request, settings)

    statuses = [c.status for c in (db, engine, tiler, queue)]
    if HealthStatus.down.value in statuses or HealthStatus.down in statuses:
        overall = HealthStatus.degraded if db.status != HealthStatus.down else HealthStatus.down
    elif HealthStatus.degraded.value in statuses or HealthStatus.degraded in statuses:
        overall = HealthStatus.degraded
    else:
        overall = HealthStatus.ok

    return HealthResponse(
        status=overall,
        version=__version__,
        contract_version="1.0.0",
        git_sha=settings.git_sha,
        time=datetime.now(UTC),
        components=HealthComponents(db=db, engine=engine, tiler=tiler, queue=queue),
        implemented_algorithms=["SAM"],
    )
