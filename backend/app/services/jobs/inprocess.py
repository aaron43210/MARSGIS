"""Default no-infra job runner: an asyncio.Queue drained by N worker tasks.

Started in the app lifespan, it offloads each job's CPU-bound engine call to a
worker thread (inside ``run_analysis_job``) and enforces a per-job wall-clock
timeout. Every status/progress write goes to the shared ``analysis_job`` row.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import Settings
from app.db.models import AnalysisJobRow
from app.db.session import session_scope
from app.errors import EngineError
from app.logging import get_logger
from app.schemas.enums import JobStatus
from app.services.engine_adapter import EngineAdapter
from app.services.jobs.tasks import _fail_job, run_analysis_job

_log = get_logger("marsgis.inprocess")


class InProcessJobRunner:
    backend = "inprocess"

    def __init__(self, settings: Settings, adapter: EngineAdapter) -> None:
        self._settings = settings
        self._adapter = adapter
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        n = self._settings.job_concurrency
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(n)]
        await self._requeue_pending()
        _log.info("inprocess.started", workers=n)

    async def stop(self) -> None:
        self._running = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._workers.clear()
        _log.info("inprocess.stopped")

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "workers": len(self._workers),
            "queue_depth": self._queue.qsize(),
            "running": self._running,
        }

    async def _requeue_pending(self) -> None:
        """Recover jobs left behind by a previous process start.

        ``queued`` rows are re-enqueued. ``running`` rows are orphans: the single
        in-process worker that owned them died with the previous process, so no
        task is executing them — mark them failed (retriable) so they leave the
        terminal-less ``running`` state, release the client's quota slot, and
        unblock pollers instead of hanging forever.
        """
        async with session_scope() as session:
            queued = (
                (
                    await session.execute(
                        select(AnalysisJobRow.id).where(
                            AnalysisJobRow.status == JobStatus.queued.value
                        )
                    )
                )
                .scalars()
                .all()
            )
            orphaned = (
                (
                    await session.execute(
                        select(AnalysisJobRow.id).where(
                            AnalysisJobRow.status == JobStatus.running.value
                        )
                    )
                )
                .scalars()
                .all()
            )
        for job_id in queued:
            await self._queue.put(job_id)
        for job_id in orphaned:
            await _fail_job(job_id, EngineError("job interrupted by a server restart"))
        if queued or orphaned:
            _log.info("inprocess.recovered", requeued=len(queued), failed_orphaned=len(orphaned))

    async def _worker(self, index: int) -> None:
        while self._running:
            try:
                job_id = await self._queue.get()
            except asyncio.CancelledError:
                break
            try:
                await asyncio.wait_for(
                    run_analysis_job(job_id, adapter=self._adapter, settings=self._settings),
                    timeout=self._settings.job_timeout_s,
                )
            except TimeoutError:
                await _fail_job(job_id, TimeoutError("job exceeded JOB_TIMEOUT_S"))
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                await _fail_job(job_id, exc)
            finally:
                self._queue.task_done()
