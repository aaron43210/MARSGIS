"""arq worker entry point (production only; JOB_BACKEND=arq).

Runs in its own process, owns its own async engine + engine adapter, pulls
``run_analysis_job`` from Redis, and writes status/progress to the SAME
analysis_job table the API reads. Not used on the default in-process path.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.services.engine_adapter import build_engine_adapter
from app.services.jobs.tasks import run_analysis_job as _run_analysis_job

_log = get_logger("marsgis.worker")


async def run_analysis_job(ctx: dict[str, Any], job_id: str) -> None:
    """arq task wrapper: delegate to the shared job body.

    arq enforces ``WorkerSettings.job_timeout`` by *cancelling* the task, which
    raises ``asyncio.CancelledError`` (a ``BaseException``) inside the shared
    body — NOT caught by its internal ``except Exception``. Without this guard
    the ``analysis_job`` row would stay ``running`` forever and keep consuming
    the client's quota slot. Mirror the in-process backend: record the failure,
    then re-raise so arq still sees the cancellation.
    """
    adapter = ctx["engine_adapter"]
    settings = ctx["settings"]
    try:
        await _run_analysis_job(job_id, adapter=adapter, settings=settings)
    except (asyncio.CancelledError, TimeoutError):
        from app.services.jobs.tasks import _fail_job

        try:
            await asyncio.shield(
                _fail_job(job_id, TimeoutError("job cancelled or exceeded JOB_TIMEOUT_S"))
            )
        except Exception:  # noqa: BLE001 - never mask the original cancellation
            _log.warning("worker.fail_job_on_cancel_errored", job_id=job_id)
        raise


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(json_logs=settings.json_logs, level=settings.log_level)
    from app.db.base import init_engine

    init_engine(settings)
    ctx["settings"] = settings
    ctx["engine_adapter"] = build_engine_adapter(settings)
    _log.info("worker.startup", engine_mode=settings.engine_mode)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    from app.db.base import dispose_engine

    await dispose_engine()
    _log.info("worker.shutdown")


def _redis_settings():
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    """arq WorkerSettings (used by ``arq app.worker.WorkerSettings`` or the
    ``marsgis-worker`` console script). Attributes are resolved at import time in
    the worker process, where arq + the production env are present."""

    functions = [run_analysis_job]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = get_settings().job_concurrency
    job_timeout = get_settings().job_timeout_s


# redis_settings must be a concrete value for arq; resolve it lazily but eagerly
# at import so the class attribute is a RedisSettings, not a property object.
try:  # pragma: no cover - prod path (arq installed)
    WorkerSettings.redis_settings = _redis_settings()  # type: ignore[assignment]
except Exception:  # arq/redis not installed in dev — worker is not used there
    WorkerSettings.redis_settings = None  # type: ignore[assignment]


def run_worker() -> None:  # pragma: no cover - prod path
    """Console-script entry (``marsgis-worker``)."""
    from arq import run_worker as _arq_run_worker

    _arq_run_worker(WorkerSettings)


if __name__ == "__main__":
    run_worker()
