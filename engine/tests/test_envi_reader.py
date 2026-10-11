"""ENVI reader tests on the synthetic cube (requires spectral + rasterio)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("spectral")
pytest.importorskip("rasterio")

from marsgis_engine.io.envi_reader import load_cube, read_block, resolve_pair


def test_resolve_pair_from_hdr_or_img(syn_cube):
    hdr, img = resolve_pair(syn_cube.hdr_path)
    assert hdr == syn_cube.hdr_path and img == syn_cube.img_path
    hdr2, img2 = resolve_pair(syn_cube.img_path)
    assert hdr2 == syn_cube.hdr_path and img2 == syn_cube.img_path


def test_shape_wavelengths_bbl_ignore(syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    assert cube.shape == (syn_cube.rows, syn_cube.cols, syn_cube.wl_nm.size)
    # wavelengths read in nm (header declares Nanometers).
    assert np.allclose(cube.wavelengths_nm, syn_cube.wl_nm, atol=1e-3)
    assert cube.ignore_value == 65535.0
    assert cube.bbl is not None
    # Bands 5 and 6 were flagged bad.
    assert not cube.bbl[5] and not cube.bbl[6]
    assert cube.n_good_bands == syn_cube.wl_nm.size - 2


def test_crs_and_transform_recovered(syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    assert cube.crs is not None
    assert not cube.crs_is_fallback  # header carried a coordinate system string
    # 1800 m pixels from the synthetic map info.
    assert abs(cube.transform.a - 1800.0) < 1e-6
    assert abs(cube.transform.e + 1800.0) < 1e-6


def test_crs_fallback_when_absent(syn_cube_no_crs):
    cube = load_cube(syn_cube_no_crs.hdr_path)
    assert cube.crs is not None
    assert cube.crs_is_fallback  # fallback Mars-2000 WKT attached


def test_read_block_nan_handling(syn_cube):
    cube = load_cube(syn_cube.hdr_path)
    block = read_block(cube, 0, cube.rows)
    assert block.dtype == np.float32
    # Ignore-value pixel -> all-NaN spectrum.
    for r, c in syn_cube.ignore_pixels:
        assert np.all(np.isnan(block[r, c, :]))
    # Planted pixel equals the carbonate end-member (finite, matches reference).
    pr, pc = syn_cube.planted[0]
    assert np.allclose(block[pr, pc, :], syn_cube.reference_values, atol=1e-3)
