"""Abuse limits for the unauthenticated public job endpoint.

Bounds the compute/DoS surface: per-client concurrency (queued+running) and a
rolling hourly submission cap, both counted from the durable analysis_job table
so the limit holds across the in-process and arq backends.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import AnalysisJobRow, utcnow
from app.errors import QuotaExceededError
from app.schemas.enums import JobStatus


async def check_quota(
    session: AsyncSession,
    fingerprint: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Raise QuotaExceededError (429) if the client is over any limit."""
    settings = settings or get_settings()

    active_stmt = (
        select(func.count())
        .select_from(AnalysisJobRow)
        .where(AnalysisJobRow.client_fingerprint == fingerprint)
        .where(AnalysisJobRow.status.in_([JobStatus.queued.value, JobStatus.running.value]))
    )
    active = int((await session.execute(active_stmt)).scalar_one())
    if active >= settings.max_concurrent_jobs_per_client:
        raise QuotaExceededError(
            "Too many concurrent jobs for this client",
            detail=(
                f"{active} queued/running >= limit "
                f"{settings.max_concurrent_jobs_per_client}. Wait for a job to finish."
            ),
        )

    since = utcnow() - timedelta(hours=1)
    hourly_stmt = (
        select(func.count())
        .select_from(AnalysisJobRow)
        .where(AnalysisJobRow.client_fingerprint == fingerprint)
        .where(AnalysisJobRow.created_at >= since)
    )
    hourly = int((await session.execute(hourly_stmt)).scalar_one())
    if hourly >= settings.max_jobs_per_hour_per_client:
        raise QuotaExceededError(
            "Hourly job limit reached for this client",
            detail=(
                f"{hourly} jobs in the last hour >= limit {settings.max_jobs_per_hour_per_client}."
            ),
        )
