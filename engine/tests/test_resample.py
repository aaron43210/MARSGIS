"""Reference resampling tests (pure numpy; spectral optional)."""

from __future__ import annotations

import numpy as np

from marsgis_engine.science.resample import resample_reference


def test_linear_matches_numpy_interp_on_overlap():
    ref_wl = np.linspace(1000.0, 2600.0, 50)
    ref_v = np.sin(ref_wl / 300.0) + 2.0
    target = np.linspace(1200.0, 2400.0, 20)
    out, valid = resample_reference(ref_wl, ref_v, target, method="linear")
    expected = np.interp(target, ref_wl, ref_v)
    assert np.allclose(out, expected)
    assert valid.all()


def test_out_of_range_bands_masked_nan():
    ref_wl = np.linspace(1500.0, 2000.0, 30)
    ref_v = np.linspace(1.0, 0.5, 30)
    target = np.array([1000.0, 1500.0, 1750.0, 2000.0, 2600.0])
    out, valid = resample_reference(ref_wl, ref_v, target, method="linear")
    assert np.isnan(out[0]) and not valid[0]  # below coverage
    assert np.isnan(out[-1]) and not valid[-1]  # above coverage
    assert valid[1] and valid[2] and valid[3]


def test_output_length_equals_target():
    ref_wl = np.linspace(1000.0, 2600.0, 40)
    ref_v = np.ones(40)
    target = np.linspace(1000.0, 2600.0, 13)
    out, valid = resample_reference(ref_wl, ref_v, target, method="linear")
    assert out.shape == target.shape == valid.shape


def test_gaussian_without_fwhm_falls_back_to_linear():
    ref_wl = np.linspace(1000.0, 2600.0, 50)
    ref_v = np.cos(ref_wl / 250.0) + 2.0
    target = np.linspace(1100.0, 2500.0, 15)
    out_g, _ = resample_reference(ref_wl, ref_v, target, method="gaussian", target_fwhm_nm=None)
    out_l, _ = resample_reference(ref_wl, ref_v, target, method="linear")
    assert np.allclose(out_g, out_l, equal_nan=True)


def test_unsorted_reference_is_sorted():
    ref_wl = np.array([2600.0, 1000.0, 1800.0, 1400.0, 2200.0])
    ref_v = np.array([0.5, 1.0, 0.8, 0.9, 0.6])
    target = np.array([1200.0, 1600.0, 2000.0])
    out, valid = resample_reference(ref_wl, ref_v, target, method="linear")
    expected = np.interp(target, np.sort(ref_wl), ref_v[np.argsort(ref_wl)])
    assert np.allclose(out, expected)
