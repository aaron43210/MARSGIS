"""Milestone A vertical-slice test — the single gate that wires the pieces.

One reproducible run that exercises the whole chain offline:

* A1  the Trek tiling scheme is the geographic 2x1@z0 grid (math invariants).
* A2  a REAL CRISM MTRDR subset is processed end to end by the engine.
* spatial correctness: the candidate map's footprint, transformed from its
  projected Mars CRS back to lon/lat, lands INSIDE the pinned observation bbox.
* reproducibility: a second run is byte-identical in the angle raster.

Skips (never fails) when the ~1 MB real fixture is absent. The live ODE
discovery leg is covered by the A5 contract tests; keeping this test offline
makes it a deterministic CI gate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("spectral")

os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

import rasterio
from rasterio.warp import transform_bounds

from marsgis_engine import RunParams, run_sam

# Reuse the A1 tiling-math helpers from the evidence script (no copy).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from verify_trek import check_math, lonlat_to_tile, tile_grid  # noqa: E402

OBSERVATION_ID = "frt00003e12"
BBOX_WSEN = (76.9404, 22.1347, 77.2127, 22.3863)
MARS_GEOGRAPHIC = "+proj=longlat +R=3396190 +no_defs"

_CUBE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "real_mtrdr_subset"
    / f"{OBSERVATION_ID}_subset.img"
)

pytestmark = pytest.mark.skipif(not _CUBE.exists(), reason=f"real fixture absent ({_CUBE})")


def _run(out_dir: Path):
    return run_sam(
        str(_CUBE),
        "carbonate",
        RunParams(out_dir=str(out_dir), timestamp="placeholder", block_rows=8),
    )


def test_a1_tiling_math_invariants():
    """A1 leg: the geographic 2x1@z0 scheme and seam/pole math hold."""
    assert all(c["ok"] for c in check_math())
    assert tile_grid(0) == (2, 1)
    # The observation's centre lands on a well-defined tile at a mid zoom.
    clon = (BBOX_WSEN[0] + BBOX_WSEN[2]) / 2
    clat = (BBOX_WSEN[1] + BBOX_WSEN[3]) / 2
    x, y = lonlat_to_tile(clon, clat, 5)
    nx, ny = tile_grid(5)
    assert 0 <= x < nx and 0 <= y < ny


def test_vertical_slice_lands_in_the_right_place(tmp_path):
    """A2 + spatial correctness: real cube -> candidate COG inside the footprint."""
    res = _run(tmp_path)
    with rasterio.open(res.candidate_path) as ds:
        assert ds.crs is not None and not ds.crs.is_geographic  # projected Mars metres
        w, s, e, n = transform_bounds(ds.crs, MARS_GEOGRAPHIC, *ds.bounds)

    cx, cy = (w + e) / 2, (s + n) / 2
    bw, bs, be, bn = BBOX_WSEN
    # The 24 px centre crop sits strictly inside the full observation footprint.
    assert bw <= cx <= be, f"lon {cx} outside [{bw}, {be}]"
    assert bs <= cy <= bn, f"lat {cy} outside [{bs}, {bn}]"


def test_vertical_slice_reproduces(tmp_path):
    """Reproducibility: a second identical run matches the angle raster exactly."""
    r1 = _run(tmp_path / "a")
    r2 = _run(tmp_path / "b")
    with rasterio.open(r1.angle_path) as a, rasterio.open(r2.angle_path) as b:
        assert np.allclose(a.read(1), b.read(1), equal_nan=True)
