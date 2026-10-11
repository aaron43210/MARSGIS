"""Wavelength unit-conversion + band-selection tests."""

from __future__ import annotations

import numpy as np
import pytest

from marsgis_engine import config
from marsgis_engine.errors import WavelengthOverlapError
from marsgis_engine.science import wavelengths as wl


def test_to_nm_from_um():
    assert np.allclose(wl.to_nm([1.0, 2.6], "Micrometers"), [1000.0, 2600.0])


def test_to_nm_from_nm_passthrough():
    assert np.allclose(wl.to_nm([1000.0, 2600.0], "Nanometers"), [1000.0, 2600.0])


def test_to_nm_unknown_units_assumes_nm():
    assert np.allclose(wl.to_nm([1000.0], "parsecs"), [1000.0])


def test_select_bands_window_and_bbl():
    w = np.linspace(900.0, 2700.0, 19)  # 100 nm spacing
    bbl = np.ones(19, dtype=bool)
    bbl[5] = False
    mask = wl.select_bands(w, bbl, (1000.0, 2600.0), mask_bad_bands=True)
    assert not mask[0]  # 900 nm below window
    assert not mask[-1]  # 2700 nm above window
    assert not mask[5]  # bad band excluded
    # Without bbl masking the bad band returns.
    mask2 = wl.select_bands(w, bbl, (1000.0, 2600.0), mask_bad_bands=False)
    assert mask2[5]


def test_overlap_mask():
    cube = np.linspace(500.0, 4000.0, 36)
    ref = np.linspace(1000.0, 2600.0, 50)
    m = wl.overlap_mask(cube, ref)
    assert m[(cube >= 1000.0) & (cube <= 2600.0)].all()
    assert not m[cube < 1000.0].any()


def test_require_overlap_raises_below_minimum():
    mask = np.zeros(50, dtype=bool)
    mask[:3] = True  # 3 < MIN_OVERLAP_BANDS
    with pytest.raises(WavelengthOverlapError):
        wl.require_overlap(mask)


def test_require_overlap_ok():
    mask = np.zeros(50, dtype=bool)
    mask[: config.MIN_OVERLAP_BANDS] = True
    assert wl.require_overlap(mask) == config.MIN_OVERLAP_BANDS


def test_band_summary_counts():
    window = np.array([False, True, True, True, True])
    bbl = np.array([True, True, False, True, True])
    final = np.array([False, True, False, True, True])
    s = wl.band_summary(window, bbl, final)
    assert s["n_bands_total"] == 5
    assert s["n_bands_in_window"] == 4
    assert s["n_bad_bands"] == 1
    assert s["n_bands_used"] == 3
