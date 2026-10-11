"""Raster serving correctness (preview, tiles, download)."""

from __future__ import annotations

OBS_ID = "frt00003e12"
REF_ID = "mica_carbonate_mg"


async def _make_result(client, poll_until_done) -> str:
    resp = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID},
    )
    assert resp.status_code == 202
    done = await poll_until_done(client, resp.json()["id"])
    assert done["status"] == "succeeded", done
    return done["result_id"]


async def test_preview_png(client, poll_until_done):
    rid = await _make_result(client, poll_until_done)
    resp = await client.get(f"/api/results/{rid}/preview.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


async def test_tile_png(client, poll_until_done):
    rid = await _make_result(client, poll_until_done)
    # z2 tile covering the Nili Fossae bbox (lon 45-90, lat 0-45).
    resp = await client.get(f"/api/results/{rid}/tiles/2/5/1.png")
    assert resp.status_code in (200, 204)
    if resp.status_code == 200:
        assert resp.headers["content-type"] == "image/png"
        assert "immutable" in resp.headers.get("cache-control", "")
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


async def test_tile_out_of_range(client, poll_until_done):
    rid = await _make_result(client, poll_until_done)
    resp = await client.get(f"/api/results/{rid}/tiles/99/0/0.png")
    assert resp.status_code == 422


async def test_download_geotiff(client, poll_until_done):
    rid = await _make_result(client, poll_until_done)
    resp = await client.get(f"/api/results/{rid}/download", params={"asset": "sam_angle"})
    assert resp.status_code == 200
    assert "tiff" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")

    mask = await client.get(f"/api/results/{rid}/download", params={"asset": "detection_mask"})
    assert mask.status_code == 200

    missing = await client.get(f"/api/results/{rid}/download", params={"asset": "match_score"})
    assert missing.status_code == 404


async def test_result_not_found(client):
    resp = await client.get("/api/results/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
