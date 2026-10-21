"""Regression tests for multi-worker job safety (audit H5).

The default config ran the in-process runner in 2 uvicorn workers. Every worker
re-enqueued all ``queued`` rows at startup, and the queued->running claim was
read-then-write, so the same job ran twice. A restarted worker also failed
jobs that were still running in its sibling, and those later flipped back to
``succeeded``.
"""

from __future__ import annotations

import os
import stat
import subprocess
import threading
import uuid
from pathlib import Path

import anyio
from sqlalchemy import func, select

from app.config import BACKEND_DIR, get_settings
from app.db.models import AnalysisJobRow, AnalysisResultRow
from app.db.session import session_scope
from app.schemas.enums import JobStatus
from app.services.jobs.tasks import _fail_job, run_analysis_job
from tests.conftest import FakeEngineAdapter


class _CountingAdapter(FakeEngineAdapter):
    def __init__(self, on_analyze=None) -> None:
        self.calls = 0
        self._lock = threading.Lock()
        self._on_analyze = on_analyze

    def analyze(self, request, progress_cb):
        with self._lock:
            self.calls += 1
        if self._on_analyze is not None:
            self._on_analyze(request)
        return super().analyze(request, progress_cb)


async def _insert_job(status: str = JobStatus.queued.value) -> str:
    job_id = uuid.uuid4().hex
    async with session_scope() as session:
        session.add(
            AnalysisJobRow(
                id=job_id,
                observation_id="frt00003e12",
                algorithm="SAM",
                reference_id="mica_carbonate_mg",
                params={},
                status=status,
            )
        )
    return job_id


async def _job(job_id: str) -> AnalysisJobRow:
    async with session_scope() as session:
        return await session.get(AnalysisJobRow, job_id)


async def test_same_job_enqueued_twice_runs_once(client_factory):
    """Two workers holding the same queued id: exactly one executes it."""
    async with client_factory():
        job_id = await _insert_job()
        adapter = _CountingAdapter()
        settings = get_settings()
        async with anyio.create_task_group() as tg:
            for _ in range(2):
                tg.start_soon(lambda: run_analysis_job(job_id, adapter=adapter, settings=settings))

        assert adapter.calls == 1
        assert (await _job(job_id)).status == JobStatus.succeeded.value
        async with session_scope() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(AnalysisResultRow)
                    .where(AnalysisResultRow.job_id == job_id)
                )
            ).scalar_one()
        assert n == 1


async def test_job_failed_mid_run_never_flips_to_succeeded(client_factory):
    """A job failed elsewhere while its engine ran must stay failed."""
    async with client_factory():
        job_id = await _insert_job()

        def _fail_from_sibling(_request) -> None:
            anyio.from_thread.run(_fail_job, job_id, RuntimeError("sibling restart recovery"))

        adapter = _CountingAdapter(on_analyze=_fail_from_sibling)
        await run_analysis_job(job_id, adapter=adapter, settings=get_settings())

        job = await _job(job_id)
        assert adapter.calls == 1
        assert job.status == JobStatus.failed.value
        assert job.result_id is None


async def test_running_job_only_reclaimed_on_arq_retry(client_factory):
    async with client_factory():
        job_id = await _insert_job(status=JobStatus.running.value)
        adapter = _CountingAdapter()

        await run_analysis_job(job_id, adapter=adapter, settings=get_settings())
        assert adapter.calls == 0  # someone else owns a running job

        await run_analysis_job(
            job_id, adapter=adapter, settings=get_settings(), reclaim_running=True
        )
        assert adapter.calls == 1
        assert (await _job(job_id)).status == JobStatus.succeeded.value


def _entrypoint_workers(tmp_path: Path, **env: str) -> str:
    """Run entrypoint.sh with a stub ``python`` that echoes its argv."""
    stub = tmp_path / "python"
    stub.write_text('#!/bin/sh\necho "$@"\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    run_env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}",
        "DATABASE_URL": "sqlite+aiosqlite:///./x.db",
        **env,
    }
    out = subprocess.run(
        ["sh", str(BACKEND_DIR / "entrypoint.sh")],
        env=run_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return out.strip().splitlines()[-1].split("--workers")[-1].strip()


def test_entrypoint_forces_single_worker_for_inprocess(tmp_path: Path):
    assert _entrypoint_workers(tmp_path, JOB_BACKEND="inprocess", WEB_CONCURRENCY="4") == "1"
    assert _entrypoint_workers(tmp_path, WEB_CONCURRENCY="4") == "1"  # inprocess is the default
    assert _entrypoint_workers(tmp_path, JOB_BACKEND="arq", WEB_CONCURRENCY="4") == "4"
