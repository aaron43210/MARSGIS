"""Optional analysis centre: validated, stored, and used to place the streamed window."""

from __future__ import annotations

import numpy as np

OBS_ID = "frt00003e12"  # footprint lon 76.9404–77.2127, lat 22.1347–22.3863
REF_ID = "mica_carbonate_mg"


async def test_center_outside_footprint_rejected(client):
    r = await client.post(
        "/api/analysis-jobs",
        json={
            "observation_id": OBS_ID,
            "reference_id": REF_ID,
            "center": {"lon": 10.0, "lat": 10.0},
        },
    )
    assert r.status_code == 422


async def test_center_inside_footprint_is_stored(client, poll_until_done):
    center = {"lon": 77.05, "lat": 22.30}
    r = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "reference_id": REF_ID, "center": center},
    )
    assert r.status_code == 202, r.text
    assert r.json()["center"] == center
    done = await poll_until_done(client, r.json()["id"])
    assert done["status"] == "succeeded", done
    prov_id = (await client.get(f"/api/results/{done['result_id']}")).json()["provenance_id"]
    prov = (await client.get(f"/api/provenance/{prov_id}")).json()
    assert prov["params"]["center"] == center


def _fake_ds(width=843, height=828):
    """Minimal stand-in for a rasterio dataset on the Mars equirectangular grid."""
    import rasterio
    from rasterio.transform import from_origin

    from app.core.constants import MARS2000_EQUIRECT_WKT

    class DS:
        pass

    ds = DS()
    ds.width, ds.height = width, height
    ds.crs = rasterio.crs.CRS.from_wkt(MARS2000_EQUIRECT_WKT)
    # ~18 m pixels starting at lon 76.94E, lat 22.39N on the Mars sphere.
    r = 3396190.0
    x0, y0 = np.radians(76.9404) * r, np.radians(22.3863) * r
    ds.transform = from_origin(x0, y0, 18.0, 18.0)
    ds.index = lambda x, y: rasterio.transform.rowcol(ds.transform, x, y)
    return ds


def test_strip_centred_on_click_and_clamped():
    from app.services.cube_fetch import _strip_start

    ds = _fake_ds()
    assert _strip_start(ds, 48, None) == 828 // 2 - 24

    # A click near the top edge moves the strip there, clamped at row 0.
    assert _strip_start(ds, 48, (76.9405, 22.3862)) == 0

    # A click lower down moves the strip off the centre, kept inside the image.
    r1 = _strip_start(ds, 48, (77.00, 22.36))
    assert r1 != 828 // 2 - 24 and 0 <= r1 <= 828 - 48

    # A strip taller than the image starts at 0.
    assert _strip_start(ds, 5000, (77.00, 22.36)) == 0


def test_cache_key_differs_per_centre():
    from app.services.jobs.tasks import subset_stem

    assert subset_stem(OBS_ID, None) == f"{OBS_ID}_strip_small"
    a, b = subset_stem(OBS_ID, (77.05, 22.30)), subset_stem(OBS_ID, (77.10, 22.20))
    # Area size is part of the cache key; the whole image ignores the centre.
    assert subset_stem(OBS_ID, None, "medium") != subset_stem(OBS_ID, None, "small")
    assert subset_stem(OBS_ID, (77.05, 22.30), "full") == subset_stem(OBS_ID, None, "full")
    assert a != b and "/" not in a and "-" not in a.replace(OBS_ID, "")
    # with_suffix must not truncate the name (it cuts at the last dot).
    from pathlib import Path

    assert Path(a).with_suffix(".img").name == f"{a}.img"


async def test_area_size_is_validated_and_stored(client, poll_until_done):
    bad = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "reference_id": REF_ID, "area": "huge"},
    )
    assert bad.status_code == 422
    r = await client.post(
        "/api/analysis-jobs",
        json={"observation_id": OBS_ID, "reference_id": REF_ID, "area": "full"},
    )
    assert r.status_code == 202 and r.json()["area"] == "full"
    done = await poll_until_done(client, r.json()["id"])
    prov_id = (await client.get(f"/api/results/{done['result_id']}")).json()["provenance_id"]
    assert (await client.get(f"/api/provenance/{prov_id}")).json()["params"]["area"] == "full"
    default = await client.post(
        "/api/analysis-jobs", json={"observation_id": OBS_ID, "reference_id": REF_ID}
    )
    assert default.json()["area"] == "small"
