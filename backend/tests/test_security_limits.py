"""Guardrails on the public, unauthenticated job endpoint."""

from __future__ import annotations

OBS_ID = "frt00003e12"
REF_ID = "mica_carbonate_mg"


async def test_unknown_algorithm_enum_422(client):
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "NOT_AN_ALGO", "reference_id": REF_ID},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


async def test_unimplemented_algorithm_422(client):
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "SID", "reference_id": REF_ID},
    )
    assert resp.status_code == 422


async def test_observation_not_found_404(client):
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": "no-such-obs", "algorithm": "SAM", "reference_id": REF_ID},
    )
    assert resp.status_code == 404


async def test_reference_not_found_404(client):
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": "no-such-ref"},
    )
    assert resp.status_code == 404


async def test_download_path_traversal_safe(client, poll_until_done):
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID},
    )
    done = await poll_until_done(client, resp.json()["id"])
    rid = done["result_id"]
    # Unknown asset keyword -> 422, never a filesystem read.
    bad = await client.get(f"/api/results/{rid}/download", params={"asset": "../../etc/passwd"})
    assert bad.status_code == 422


async def test_hourly_quota_429(client_factory, poll_until_done):
    async with client_factory(MAX_JOBS_PER_HOUR_PER_CLIENT="2") as client:
        body = {"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID}
        r1 = await client.post("/api/analysis-jobs", json=body)
        r2 = await client.post("/api/analysis-jobs", json=body)
        r3 = await client.post("/api/analysis-jobs", json=body)
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r3.status_code == 429
        assert r3.json()["code"] in ("quota_exceeded", "job_limit_exceeded")


async def test_require_api_key_blocks(client_factory):
    async with client_factory(REQUIRE_API_KEY="true", API_KEYS='["secret-key"]') as client:
        body = {"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID}
        blocked = await client.post("/api/analysis-jobs", json=body)
        assert blocked.status_code == 401

        allowed = await client.post(
            "/api/analysis-jobs", json=body, headers={"X-API-Key": "secret-key"}
        )
        assert allowed.status_code == 202
