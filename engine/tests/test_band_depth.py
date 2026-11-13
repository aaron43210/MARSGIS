"""Band-depth SAM tells minerals apart on the bundled sample (known answers)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
import rasterio

from marsgis_engine import RunParams, inspect_pixel, run_sam

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
CUBE = SAMPLE / "sample_crism_nili.img"
TRUTH = json.loads((SAMPLE / "sample_truth.json").read_text())


def _region(name, shape):
    r = TRUTH[name]
    m = np.zeros(shape, bool)
    m[r["line"][0] : r["line"][1], r["sample"][0] : r["sample"][1]] = True
    return m


def _angles(tmp_path, mineral, **kw):
    p = RunParams(
        out_dir=str(tmp_path / mineral),
        out_prefix="r",
        timestamp="placeholder",
        band_depth=True,
        **kw,
    )
    res = run_sam(str(CUBE), mineral, p)
    with rasterio.open(res.angle_path) as ds:
        return ds.read(1), res


def test_carbonate_found_exactly_where_planted(tmp_path):
    a, res = _angles(tmp_path, "carbonate", threshold_rad=0.30)
    carb = _region("carbonate_region", a.shape)
    hit = np.isfinite(a) & (a <= 0.30)
    assert hit[carb].all()  # recall 1.0
    assert not hit[~carb].any()  # precision 1.0
    assert res.stats["band_depth"] is True


def test_best_match_separates_carbonate_and_olivine(tmp_path):
    c, _ = _angles(tmp_path, "carbonate")
    o, _ = _angles(tmp_path, "olivine")
    carb = _region("carbonate_region", c.shape)
    oliv = _region("olivine_region", c.shape)
    # Measured: carbonate wins 98.6% of planted carbonate pixels (2 near-ties), olivine 100%.
    assert (c[carb] < o[carb]).mean() >= 0.98
    assert (o[oliv] < c[oliv]).all()


def test_uses_the_minerals_own_window(tmp_path):
    _, res = _angles(tmp_path, "carbonate")
    prov = json.loads(Path(res.provenance_path).read_text())
    assert prov["wavelength_alignment"]["cube_window_nm"] == [2200.0, 2600.0]


def test_inspector_matches_raster_in_band_depth_mode(tmp_path):
    a, _ = _angles(tmp_path, "carbonate")
    p = RunParams(band_depth=True)
    for r, c in [(13, 13), (40, 40), (2, 30)]:
        out = inspect_pixel(str(CUBE), "carbonate", p, r, c)
        assert out["band_depth"] is True and out["window_nm"] == [2200.0, 2600.0]
        if np.isfinite(a[r, c]):
            assert out["angle_rad"] == pytest.approx(float(a[r, c]), abs=1e-5)
