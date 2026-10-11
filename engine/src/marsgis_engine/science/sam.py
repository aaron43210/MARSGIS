"""Vectorized Spectral Angle Mapper (SAM) core.

The spectral angle between a test spectrum ``t`` and a reference ``r`` over a
set of bands is::

    angle = arccos( clip( (t . r) / (||t|| * ||r||), -1, 1 ) )

Properties (exercised by test_sam.py):

* identical spectrum              -> 0
* positively scaled spectrum k*t  -> 0        (albedo / illumination invariant)
* orthogonal spectra              -> pi/2
* t=[1,0], r=[1,1]                -> pi/4

NaN handling is pairwise per pixel: for each pixel only the bands finite in
*that* pixel AND in the reference contribute. A pixel with fewer than
``config.MIN_OVERLAP_BANDS`` contributing bands, or a zero-norm spectrum, yields
NaN (nodata). A non-finite reference band is dropped pairwise (it never poisons
the whole scene), so the pipeline may pass a reference that is not finite on
every band.

Everything is vectorized over ``(npix, nbands)`` so a row-block of a cube is one
numpy call; no full-cube materialization and no Python per-pixel loop.
"""

from __future__ import annotations

import numpy as np

from .. import config


def sam_angles(
    pixels: np.ndarray,
    reference: np.ndarray,
    *,
    min_bands: int = config.MIN_OVERLAP_BANDS,
) -> np.ndarray:
    """Spectral angle (radians) between each pixel and the reference.

    Parameters
    ----------
    pixels:
        Array of shape ``(npix, nbands)`` (float). May contain NaN for bad /
        ignored bands; those are excluded per pixel.
    reference:
        1-D array of shape ``(nbands,)`` aligned 1:1 with ``pixels`` columns.
        Bands where the reference is non-finite are dropped pairwise (they do
        not contribute to any pixel's angle).
    min_bands:
        Minimum finite bands a pixel needs for a defined angle; below this the
        result is NaN.

    Returns
    -------
    np.ndarray
        Shape ``(npix,)`` float64 angles in radians; NaN where undefined.
    """
    t = np.asarray(pixels, dtype=np.float64)
    r = np.asarray(reference, dtype=np.float64).reshape(-1)
    if t.ndim != 2:
        t = t.reshape(-1, r.size)
    if t.shape[1] != r.size:
        raise ValueError(f"band mismatch: pixels have {t.shape[1]} bands, reference has {r.size}")

    finite = np.isfinite(t) & np.isfinite(r).reshape(1, -1)  # (npix, nbands)
    # Zero-fill non-finite entries (pixel OR reference) so excluded bands add
    # nothing to the sums; a single non-finite reference band is thus dropped
    # pairwise instead of poisoning every pixel to NaN (silent total data loss).
    t_filled = np.where(finite, t, 0.0)
    r_filled = np.where(np.isfinite(r), r, 0.0)
    r_row = r_filled.reshape(1, -1)

    # Pairwise dot product and norms over the per-pixel finite band set.
    dot = np.einsum("ij,ij->i", t_filled, finite * r_row)
    t_norm = np.sqrt(np.einsum("ij,ij->i", t_filled, t_filled))
    r_sq = r_row * r_row
    r_norm = np.sqrt(np.einsum("ij,ij->i", finite.astype(np.float64), r_sq))

    valid_count = finite.sum(axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        cos = dot / (t_norm * r_norm)
    cos = np.clip(cos, -1.0, 1.0)
    angles = np.arccos(cos)

    undefined = (
        (valid_count < int(min_bands)) | (t_norm <= 0.0) | (r_norm <= 0.0) | ~np.isfinite(angles)
    )
    angles[undefined] = np.nan
    return angles


def threshold_mask(angles: np.ndarray, threshold_rad: float) -> np.ndarray:
    """Classify angles into the candidate mask uint8 {0, 1, 255}.

    * 1   -> candidate (finite angle <= threshold)
    * 0   -> non-match (finite angle > threshold)
    * 255 -> nodata (angle is NaN)
    """
    a = np.asarray(angles, dtype=np.float64)
    out = np.full(a.shape, config.CANDIDATE_NODATA, dtype=np.uint8)
    finite = np.isfinite(a)
    out[finite & (a <= float(threshold_rad))] = config.CANDIDATE_MATCH
    out[finite & (a > float(threshold_rad))] = config.CANDIDATE_NON_MATCH
    return out
