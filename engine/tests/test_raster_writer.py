"""COG output tests (requires rasterio; validates COG structure)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("spectral")

import rasterio

from marsgis_engine import config
from marsgis_engine.io.envi_reader import load_cube
from marsgis_engine.io.raster_writer import write_angle, write_candidate


def test_write_angle_is_cog_float32_nan(tmp_path, syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    angle = np.random.default_rng(0).uniform(0, 1.5, size=(cube.rows, cube.cols)).astype(np.float32)
    angle[0, 0] = np.nan
    out = write_angle(tmp_path / "a_SAM_angle.tif", angle, cube)
    with rasterio.open(out) as ds:
        assert ds.dtypes[0] == "float32"
        assert ds.count == 1
        assert np.isnan(ds.nodata)
        # CRS + transform preserved from the cube.
        assert ds.transform.a == cube.transform.a
        assert ds.crs is not None
        tags = ds.tags()
        assert tags.get("ALGORITHM") == "SAM"


def test_write_candidate_is_cog_uint8(tmp_path, syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    mask = np.zeros((cube.rows, cube.cols), dtype=np.uint8)
    mask[1, 1] = config.CANDIDATE_MATCH
    mask[-1, -1] = config.CANDIDATE_NODATA
    out = write_candidate(tmp_path / "a_SAM_candidate.tif", mask, cube)
    with rasterio.open(out) as ds:
        assert ds.dtypes[0] == "uint8"
        assert ds.nodata == 255
        assert ds.transform.a == cube.transform.a
        read = ds.read(1)
        assert read[1, 1] == 1
        assert read[-1, -1] == 255


def test_cog_structure_tiled(tmp_path, syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    angle = np.zeros((cube.rows, cube.cols), dtype=np.float32)
    out = write_angle(tmp_path / "t_SAM_angle.tif", angle, cube)
    with rasterio.open(out) as ds:
        assert ds.profile.get("tiled", False) is True
