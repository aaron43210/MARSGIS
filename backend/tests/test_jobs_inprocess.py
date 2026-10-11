"""End-to-end job lifecycle on the in-process backend (fake engine)."""

from __future__ import annotations

OBS_ID = "frt00003e12"
REF_ID = "mica_carbonate_mg"


async def _run_job(client, poll_until_done) -> dict:
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID},
    )
    assert resp.status_code == 202, resp.text
    created = resp.json()
    assert created["status"] == "queued"
    assert resp.headers.get("Location", "").endswith(created["id"])
    return await poll_until_done(client, created["id"])


async def test_job_succeeds_and_produces_result(client, poll_until_done):
    done = await _run_job(client, poll_until_done)
    assert done["status"] == "succeeded", done
    assert done["progress"] == 1.0
    assert done["result_id"]

    result = (await client.get(f"/api/results/{done['result_id']}")).json()
    assert result["algorithm"] == "SAM"
    assert result["caveat"]
    assert result["summary_stats"]["caveat"]
    assert result["legend"]["caveat"]
    assert result["map_layer"]["type"] == "result_tiles"
    assert result["map_layer"]["source"]["tile_order"] == "zxy"
    assert len(result["bounds"]) == 4
    assert result["value_range"][0] == 0.0

    # The matched block in the synthetic COG must register as candidate pixels.
    stats = result["summary_stats"]
    assert stats["valid_pixel_count"] > 0
    assert stats["detected_pixel_count"] > 0


async def test_provenance_record(client, poll_until_done):
    done = await _run_job(client, poll_until_done)
    result = (await client.get(f"/api/results/{done['result_id']}")).json()
    prov_id = result["provenance_id"]

    prov = (await client.get(f"/api/provenance/{prov_id}")).json()
    assert prov["engine_image"]
    assert prov["engine_version"]
    assert prov["caveat"]
    assert OBS_ID in prov["source_ids"]
    # Synthetic input must be recorded honestly in the reproducibility record.
    assert prov["params"].get("synthetic_input") is True


async def test_job_listing(client, poll_until_done):
    await _run_job(client, poll_until_done)
    resp = await client.get("/api/analysis-jobs", params={"observation_id": OBS_ID})
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] >= 1
    assert all(j["observation_id"] == OBS_ID for j in page["items"])


async def test_idempotency_key_dedupes(client):
    headers = {"Idempotency-Key": "test-key-123"}
    body = {"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID}
    first = await client.post("/api/analysis-jobs", json=body, headers=headers)
    second = await client.post("/api/analysis-jobs", json=body, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
