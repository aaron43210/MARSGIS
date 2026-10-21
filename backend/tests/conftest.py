"""Offline test harness: temp SQLite + seeded data + a FakeEngineAdapter.

The fake adapter writes a tiny synthetic Mars-geographic COG instead of calling
the real engine, so the full job -> result -> tile flow runs with no engine
install and no network. Each test gets a fresh, isolated, seeded database.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from tests.fixtures.make_sample_cog import make_sample_cog


class FakeEngineAdapter:
    """Deterministic offline engine stand-in (writes a synthetic COG)."""

    def version(self) -> str:
        return "fake-engine-1.0.0"

    def analyze(self, request, progress_cb):
        from app.services.engine_adapter import EngineResult

        progress_cb(0.2, "fake engine: writing synthetic COG")
        angle_path, mask_path = make_sample_cog(
            request.out_dir, request.result_id, threshold_rad=request.threshold_rad
        )
        progress_cb(0.8, "fake engine: done")
        return EngineResult(
            angle_path=angle_path,
            mask_path=mask_path,
            score_path=None,
            provenance={
                "disclaimer": "SYNTHETIC test output; not a real detection.",
                "software": {"name": "fake-engine", "version": "1.0.0"},
            },
            stats={"n_valid_pixels": 0},
            engine_version="fake-engine-1.0.0",
            engine_image="local/fake-engine:test",
            is_synthetic=True,
        )


def _base_env(storage: Path, db_path: Path) -> dict[str, str]:
    return {
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "STORAGE_ROOT": str(storage),
        "SEED_ON_STARTUP": "true",
        "RUN_MIGRATIONS_ON_STARTUP": "true",
        "JOB_BACKEND": "inprocess",
        "ENGINE_MODE": "inprocess",
        "ENGINE_CUBE_SOURCE": "sample",
        "JOB_CONCURRENCY": "2",
        "MAX_CONCURRENT_JOBS_PER_CLIENT": "5",
        "MAX_JOBS_PER_HOUR_PER_CLIENT": "50",
        "REQUIRE_API_KEY": "false",
    }


@contextlib.asynccontextmanager
async def _make_client(tmp_path: Path, monkeypatch, env_overrides: dict[str, str] | None = None):
    from httpx import ASGITransport, AsyncClient

    storage = tmp_path / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    db_path = storage / "test.db"

    env = _base_env(storage, db_path)
    env.update(env_overrides or {})
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from app.config import get_settings

    get_settings.cache_clear()

    import app.services.engine_adapter as ea

    monkeypatch.setattr(ea, "build_engine_adapter", lambda settings=None: FakeEngineAdapter())

    from app.db.base import dispose_engine
    from app.main import create_app

    await dispose_engine()
    application = create_app()

    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        # Stopping the runner cancels the job tasks but not their engine threads,
        # so a test that only enqueues jobs would leave GDAL writing while the next
        # test rewrites os.environ, which can segfault on Linux. Drain them first.
        await _wait_for_jobs_to_settle()
    await dispose_engine()
    get_settings.cache_clear()


async def _wait_for_jobs_to_settle(timeout_s: float = 30.0) -> None:
    import anyio
    from sqlalchemy import func, select

    from app.db.models import AnalysisJobRow
    from app.db.session import session_scope

    with anyio.move_on_after(timeout_s):
        while True:
            async with session_scope() as session:
                active = (
                    await session.execute(
                        select(func.count())
                        .select_from(AnalysisJobRow)
                        .where(AnalysisJobRow.status.in_(("queued", "running")))
                    )
                ).scalar_one()
            if not active:
                return
            await anyio.sleep(0.05)


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch) -> AsyncIterator[object]:
    async with _make_client(tmp_path, monkeypatch) as c:
        yield c


@pytest.fixture
def client_factory(tmp_path: Path, monkeypatch):
    """Return an async-context factory for a client with env overrides."""

    def _factory(**env_overrides: str):
        return _make_client(tmp_path, monkeypatch, env_overrides)

    return _factory


async def _poll_until_done(client, job_id: str, *, tries: int = 200) -> dict:
    import anyio

    for _ in range(tries):
        resp = await client.get(f"/api/analysis-jobs/{job_id}")
        data = resp.json()
        if data["status"] in ("succeeded", "failed"):
            return data
        await anyio.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish in time")


@pytest.fixture
def poll_until_done():
    return _poll_until_done
