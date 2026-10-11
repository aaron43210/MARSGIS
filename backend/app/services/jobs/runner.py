"""JobRunner protocol + factory.

Both backends report status purely via the ``analysis_job`` row, so the HTTP API
and polling are backend-agnostic. The default is the no-infra in-process runner;
``JOB_BACKEND=arq`` selects the Redis-backed runner (execution lives in a
separate ``marsgis-worker`` process).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.config import Settings, get_settings
from app.services.engine_adapter import EngineAdapter, build_engine_adapter


@runtime_checkable
class JobRunner(Protocol):
    backend: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def enqueue(self, job_id: str) -> None: ...
    def status(self) -> dict: ...


def build_runner(
    settings: Settings | None = None,
    adapter: EngineAdapter | None = None,
) -> JobRunner:
    settings = settings or get_settings()
    adapter = adapter or build_engine_adapter(settings)
    if settings.job_backend == "arq":
        from app.services.jobs.arq_runner import ArqJobRunner

        return ArqJobRunner(settings)
    from app.services.jobs.inprocess import InProcessJobRunner

    return InProcessJobRunner(settings, adapter)
