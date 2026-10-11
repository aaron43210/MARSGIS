"""Regression tests for the adversarial-review findings.

Each test pins a specific bug fixed during integration so it cannot silently
return:
- oversized chunked (no Content-Length) request bodies are rejected (413);
- the per-client fingerprint ignores the spoofable X-Forwarded-For by default;
- a job orphaned in 'running' by a crash/restart is recovered (failed) on the
  next startup instead of hanging forever and leaking the client's quota slot.
"""

from __future__ import annotations


async def test_oversized_chunked_body_rejected(client):
    """Finding: the body-size cap must hold for a chunked body with no
    Content-Length, not only for a declared Content-Length."""
    big = b'{"observation_id":"x","padding":"' + b"A" * 2_000_000 + b'"}'

    async def agen():
        yield big

    resp = await client.post(
        "/api/analysis-jobs", content=agen(), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 413


async def test_normal_body_still_accepted(client, poll_until_done):
    """The buffering body-guard must not break a normal small POST."""
    resp = await client.post(
        "/api/analysis-jobs",
        json={
            "observation_id": "frt00003e12",
            "algorithm": "SAM",
            "reference_id": "mica_carbonate_mg",
        },
    )
    assert resp.status_code == 202


def test_forwarded_for_not_trusted_by_default():
    """Finding: quota/rate keys must not trust the client-supplied XFF header
    (otherwise limits are bypassable by rotating X-Forwarded-For)."""
    from starlette.requests import Request

    from app.config import get_settings
    from app.deps import client_fingerprint

    get_settings.cache_clear()

    def _req(xff: str | None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.5", 5555)})

    fp_spoof_a = client_fingerprint(_req("1.2.3.4"))
    fp_spoof_b = client_fingerprint(_req("9.9.9.9"))
    fp_none = client_fingerprint(_req(None))
    # All identical: XFF is ignored, the real peer (10.0.0.5) is used.
    assert fp_spoof_a == fp_spoof_b == fp_none


async def test_orphaned_running_job_recovered_on_startup(client_factory):
    """Finding: a job left 'running' by a crash/restart must be recovered on the
    next startup (marked failed+retriable), freeing the client's quota slot."""
    from app.db.models import AnalysisJobRow
    from app.db.session import session_scope
    from app.schemas.enums import JobStatus

    async with client_factory() as c:
        # Create and complete a job, then force it back to 'running' to simulate
        # a process that died mid-run (DB row durable, no worker executing it).
        r = await c.post(
            "/api/analysis-jobs",
            json={
                "observation_id": "frt00003e12",
                "algorithm": "SAM",
                "reference_id": "mica_carbonate_mg",
            },
        )
        job_id = r.json()["id"]
        import anyio

        for _ in range(200):
            d = (await c.get(f"/api/analysis-jobs/{job_id}")).json()
            if d["status"] in ("succeeded", "failed"):
                break
            await anyio.sleep(0.05)

        async with session_scope() as session:
            job = await session.get(AnalysisJobRow, job_id)
            job.status = JobStatus.running.value
            job.result_id = None
            job.finished_at = None
            session.add(job)

        # A fresh runner's startup recovery should fail the orphan.
        from app.config import get_settings
        from app.services.jobs.inprocess import InProcessJobRunner

        class _StubAdapter:
            def version(self) -> str:
                return "stub"

            def analyze(self, *a, **k):  # pragma: no cover - not called here
                raise AssertionError("adapter should not run during recovery")

        runner = InProcessJobRunner(get_settings(), _StubAdapter())
        await runner._requeue_pending()

        async with session_scope() as session:
            job = await session.get(AnalysisJobRow, job_id)
            assert job.status == JobStatus.failed.value
            assert job.error is not None
            assert job.error.get("retriable") is True
            assert job.finished_at is not None
