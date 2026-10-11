"""SAM correctness unit tests (pure numpy; no I/O)."""

from __future__ import annotations

import math

import numpy as np

from marsgis_engine.science.sam import sam_angles, threshold_mask


def test_identical_vectors_zero_angle():
    r = np.array([0.2, 0.5, 0.9, 0.3, 0.7, 0.6, 0.8, 0.4, 0.55, 0.65, 0.75, 0.45])
    pixels = np.tile(r, (3, 1))
    angles = sam_angles(pixels, r)
    assert np.allclose(angles, 0.0, atol=1e-6)


def test_scaled_vector_albedo_invariant():
    r = np.linspace(0.1, 1.0, 15)
    pixels = np.vstack([r * 0.5, r * 2.0, r * 7.3])
    angles = sam_angles(pixels, r)
    assert np.allclose(angles, 0.0, atol=1e-6)


def test_orthogonal_vectors_half_pi():
    # Build two orthogonal non-negative vectors over >= MIN_OVERLAP_BANDS bands.
    n = 12
    t = np.zeros(n)
    r = np.zeros(n)
    t[: n // 2] = 1.0
    r[n // 2 :] = 1.0
    angles = sam_angles(t.reshape(1, -1), r)
    assert math.isclose(angles[0], math.pi / 2, rel_tol=1e-6)


def test_known_quarter_pi():
    # t=[1,0], r=[1,1] -> pi/4 (2-band angle, min_bands lowered for the test).
    angle = sam_angles(np.array([[1.0, 0.0]]), np.array([1.0, 1.0]), min_bands=2)
    assert math.isclose(angle[0], math.pi / 4, rel_tol=1e-6)


def test_nan_pixel_yields_nan():
    r = np.linspace(0.2, 1.0, 12)
    pix = r.copy().reshape(1, -1)
    pix[0, :] = np.nan
    angles = sam_angles(pix, r)
    assert np.isnan(angles[0])


def test_too_few_finite_bands_nan():
    r = np.linspace(0.2, 1.0, 12)
    pix = np.full((1, 12), np.nan)
    pix[0, :3] = r[:3]  # only 3 finite bands < MIN_OVERLAP_BANDS (10)
    angles = sam_angles(pix, r)
    assert np.isnan(angles[0])


def test_zero_norm_pixel_nan():
    r = np.linspace(0.2, 1.0, 12)
    pix = np.zeros((1, 12))
    angles = sam_angles(pix, r)
    assert np.isnan(angles[0])


def test_pairwise_nan_band_exclusion():
    # A single NaN band in the pixel should be excluded, not poison the angle.
    r = np.linspace(0.2, 1.0, 12)
    pix = r.copy().reshape(1, -1)
    pix[0, 4] = np.nan
    angles = sam_angles(pix, r)
    assert np.isfinite(angles[0])
    assert angles[0] < 1e-6  # still essentially identical over the kept bands


def test_threshold_mask_values():
    angles = np.array([0.0, 0.05, 0.1, 0.2, np.nan])
    mask = threshold_mask(angles, 0.1)
    assert mask.tolist() == [1, 1, 1, 0, 255]
    assert mask.dtype == np.uint8


def test_non_finite_reference_band_is_dropped_not_poisoning():
    # Regression: a single non-finite reference band (e.g. produced by continuum
    # removal of a non-positive value) must be excluded pairwise, NOT turn every
    # pixel's angle into NaN (which would be silent total data loss).
    ref = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    pix = np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 5.0],  # matches ref on the finite bands -> ~0
            [5.0, 4.0, 3.0, 2.0, 1.0],  # clearly different -> larger angle
        ]
    )
    angles = sam_angles(pix, ref, min_bands=3)
    assert np.isfinite(angles).all()  # NOT all-NaN
    assert angles[0] < 1e-9
    assert angles[1] > angles[0]
