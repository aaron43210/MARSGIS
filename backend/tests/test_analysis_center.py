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


def test_window_centred_on_click_and_clamped():
    from app.services.cube_fetch import _window_origin

    ds = _fake_ds()
    centre = _window_origin(ds, 48, None)
    assert centre == (843 // 2 - 24, 828 // 2 - 24)

    # A click near the top-left corner moves the window there, clamped at 0.
    c0, r0 = _window_origin(ds, 48, (76.9405, 22.3862))
    assert (c0, r0) == (0, 0)

    # A click inside moves the window off the image centre.
    c1, r1 = _window_origin(ds, 48, (77.00, 22.36))
    assert (c1, r1) != centre
    assert 0 <= c1 <= 843 - 48 and 0 <= r1 <= 828 - 48


def test_cache_key_differs_per_centre():
    from app.services.jobs.tasks import subset_stem

    assert subset_stem(OBS_ID, None) == f"{OBS_ID}_subset"
    a, b = subset_stem(OBS_ID, (77.05, 22.30)), subset_stem(OBS_ID, (77.10, 22.20))
    assert a != b and "/" not in a and "-" not in a.replace(OBS_ID, "")
