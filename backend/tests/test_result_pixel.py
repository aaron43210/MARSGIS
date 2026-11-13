"""Per-pixel inspector: real spectra, real angles, no placeholders."""

from __future__ import annotations

OBS_ID = "frt00003e12"
REF_ID = "mica_carbonate_mg"


async def _make_result(client, poll_until_done, **params) -> dict:
    body = {"observation_id": OBS_ID, "algorithm": "SAM", "reference_id": REF_ID}
    if params:
        body["params"] = params
    resp = await client.post("/api/analysis-jobs", json=body)
    assert resp.status_code == 202, resp.text
    done = await poll_until_done(client, resp.json()["id"])
    assert done["status"] == "succeeded", done
    return (await client.get(f"/api/results/{done['result_id']}")).json()


def _cell(bounds, fx, fy):
    w, s, e, n = bounds
    return (w + (e - w) * fx, n - (n - s) * fy)


async def test_pixel_returns_real_spectrum_and_angle(real_client, poll_until_done):
    res = await _make_result(real_client, poll_until_done)
    # Sample cube: planted carbonate block at lines/samples 7..19 of 48.
    lon, lat = _cell(res["bounds"], 13 / 48, 13 / 48)
    r = await real_client.get(f"/api/results/{res['id']}/pixel", params={"lon": lon, "lat": lat})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["inside"] is True
    assert len(p["wavelength_nm"]) == len(p["pixel"]) == len(p["reference"]) > 10
    # Same number SAM wrote to the result raster.
    assert abs(p["angle_rad"] - p["raster_angle_rad"]) < 1e-5
    assert p["is_candidate"] is True
    assert p["synthetic_input"] is True  # tests run in sample mode
    assert res["synthetic_input"] is True  # the result itself says it is practice data


async def test_different_pixels_differ(real_client, poll_until_done):
    res = await _make_result(real_client, poll_until_done)

    def at(fx: float, fy: float) -> dict[str, float]:
        lon, lat = _cell(res["bounds"], fx, fy)
        return {"lon": lon, "lat": lat}

    a = (
        await real_client.get(f"/api/results/{res['id']}/pixel", params=at(13 / 48, 13 / 48))
    ).json()
    b = (
        await real_client.get(f"/api/results/{res['id']}/pixel", params=at(44 / 48, 44 / 48))
    ).json()
    assert a["pixel"] != b["pixel"]
    assert a["angle_rad"] != b["angle_rad"]
    assert b["is_candidate"] is False


async def test_threshold_changes_the_result(real_client, poll_until_done):
    tight = await _make_result(real_client, poll_until_done, threshold_rad=0.002)
    loose = await _make_result(real_client, poll_until_done, threshold_rad=0.10)
    t = tight["summary_stats"]["detected_pixel_count"]
    l_ = loose["summary_stats"]["detected_pixel_count"]
    assert t < l_, (t, l_)


async def test_pixel_outside_result(real_client, poll_until_done):
    res = await _make_result(real_client, poll_until_done)
    r = await real_client.get(
        f"/api/results/{res['id']}/pixel", params={"lon": -150.0, "lat": -60.0}
    )
    assert r.status_code == 200
    assert r.json()["inside"] is False


async def test_pixel_validation_and_404(real_client):
    url = "/api/results/nope/pixel"
    assert (await real_client.get(url, params={"lon": 0, "lat": 0})).status_code == 404
    assert (await real_client.get(url, params={"lon": 999, "lat": 0})).status_code == 422


async def test_app_does_not_hide_envi_sidecars(real_client):
    """No process-wide GDAL setting may stop the engine reading a cube's own .hdr/CRS.

    A global GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR (once set for the elevation DEM)
    hid the ENVI header from GDAL, so every cube silently got the fallback CRS and
    real archive cubes could not be opened at all.
    """
    import os

    from marsgis_engine import load_cube

    from app.config import get_settings

    assert os.environ.get("GDAL_DISABLE_READDIR_ON_OPEN") != "EMPTY_DIR"
    cube = load_cube(str(get_settings().sample_cube_abspath))
    assert cube.crs_is_fallback is False
