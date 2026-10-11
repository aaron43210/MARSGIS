"""Thread-safe progress bridge from the compute thread to the DB (on the loop).

The CPU-bound engine call runs in a worker thread via ``anyio.to_thread``. The
adapter reports progress through a plain ``(fraction, message)`` callback; this
module turns that callback into throttled async DB writes executed back on the
event loop, so ``GET /api/analysis-jobs/{id}`` reflects live progress.
"""

from __future__ import annotations

from collections.abc import Callable

import anyio

from app.db.models import AnalysisJobRow, utcnow
from app.db.session import session_scope
from app.logging import get_logger
from app.schemas.enums import TERMINAL_JOB_STATUSES, JobStatus

_log = get_logger("marsgis.progress")


async def update_progress(job_id: str, fraction: float, message: str) -> None:
    frac = max(0.0, min(1.0, float(fraction)))
    async with session_scope() as session:
        job = await session.get(AnalysisJobRow, job_id)
        if job is None or JobStatus(job.status) in TERMINAL_JOB_STATUSES:
            return
        job.progress = frac
        job.message = message
        job.updated_at = utcnow()
        session.add(job)


def make_progress_cb(job_id: str, *, min_delta: float = 0.02) -> Callable[[float, str], None]:
    """Return a thread-safe progress callback that writes to the DB (throttled)."""
    state = {"last": -1.0}

    def _cb(fraction: float, message: str) -> None:
        if fraction - state["last"] < min_delta and fraction < 1.0:
            return
        state["last"] = fraction
        try:
            anyio.from_thread.run(update_progress, job_id, fraction, message)
        except Exception as exc:  # pragma: no cover - best-effort progress only
            _log.debug("progress.bridge_failed", error=str(exc))

    return _cb
