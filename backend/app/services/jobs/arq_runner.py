"""Optional production enqueue path (arq + Redis).

The runner only enqueues; execution happens in the separate ``marsgis-worker``
process (``app/worker.py``), which updates the same ``analysis_job`` row, so the
HTTP API is unchanged.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.logging import get_logger

_log = get_logger("marsgis.arq")


def _redis_settings(settings: Settings):
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(settings.redis_url)


class ArqJobRunner:
    backend = "arq"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: Any | None = None

    async def start(self) -> None:
        from arq import create_pool

        self._pool = await create_pool(_redis_settings(self._settings))
        _log.info("arq.pool_ready", redis=self._settings.redis_url)

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
        _log.info("arq.pool_closed")

    async def enqueue(self, job_id: str) -> None:
        if self._pool is None:
            await self.start()
        assert self._pool is not None
        await self._pool.enqueue_job("run_analysis_job", job_id)

    def status(self) -> dict:
        return {"backend": self.backend, "connected": self._pool is not None}
