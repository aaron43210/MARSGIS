"""Continuum-removal tests (pure numpy)."""

from __future__ import annotations

import numpy as np

from marsgis_engine.science.continuum import continuum_removed, remove_reference_continuum


def test_flat_spectrum_all_ones():
    wl = np.linspace(1000.0, 2600.0, 30)
    flat = np.full_like(wl, 1.3)
    out = continuum_removed(flat, wl)
    assert np.allclose(out, 1.0, atol=1e-9)


def test_sloped_spectrum_all_ones():
    # A monotonic linear slope is its own convex hull -> ratio 1 everywhere.
    wl = np.linspace(1000.0, 2600.0, 30)
    sloped = 1.0 + 0.0005 * (wl - wl.min())
    out = continuum_removed(sloped, wl)
    assert np.allclose(out, 1.0, atol=1e-6)


def test_single_absorption_band_depth():
    wl = np.linspace(1000.0, 2600.0, 40)
    spec = np.ones_like(wl)
    dip = np.argmin(np.abs(wl - 2300.0))
    spec[dip] = 0.6  # a 40% absorption
    out = continuum_removed(spec, wl)
    assert out[dip] < 1.0
    assert out[dip] < 0.7
    # Hull endpoints untouched.
    assert np.isclose(out[0], 1.0, atol=1e-6)
    assert np.isclose(out[-1], 1.0, atol=1e-6)
    # Everything in (0, 1].
    assert np.all(out[np.isfinite(out)] <= 1.0 + 1e-9)


def test_nan_safe():
    wl = np.linspace(1000.0, 2600.0, 20)
    spec = np.ones_like(wl)
    spec[5] = np.nan
    spec[10] = 0.5
    out = continuum_removed(spec, wl)
    assert np.isnan(out[5])
    assert out[10] < 1.0


def test_2d_stack_matches_1d():
    wl = np.linspace(1000.0, 2600.0, 25)
    a = np.ones_like(wl)
    a[8] = 0.7
    b = np.ones_like(wl)
    b[15] = 0.5
    stack = np.vstack([a, b])
    out = continuum_removed(stack, wl)
    assert np.allclose(out[0], remove_reference_continuum(a, wl), equal_nan=True)
    assert np.allclose(out[1], remove_reference_continuum(b, wl), equal_nan=True)


def test_monotone_hull_above_signal():
    rng = np.random.default_rng(0)
    wl = np.linspace(1000.0, 2600.0, 50)
    spec = 1.0 - 0.3 * np.exp(-0.5 * ((wl - 2300.0) / 50.0) ** 2) + rng.normal(0, 0.001, wl.size)
    out = continuum_removed(spec, wl)
    # Continuum-removed values never exceed ~1 (hull is the upper boundary).
    assert np.nanmax(out) <= 1.0 + 1e-6
