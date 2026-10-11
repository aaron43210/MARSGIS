"""Optional convex-hull continuum removal.

For each spectrum the *upper* convex hull over ``(wavelength, value)`` points is
computed (monotone-chain), linearly interpolated across all bands, and the
spectrum is divided by that hull. The result lies in ``(0, 1]`` where
``1 - value`` is the band depth. Flat / hull-touching bands map to ~1.0;
absorption bands dip below 1.0.

SAM is already invariant to multiplicative albedo scaling, so continuum removal
is an *enhancement* (it emphasises band shape and partially mitigates the
ratioed-MICA vs un-ratioed-scene mismatch), not a requirement. It is applied to
both the pixel spectra and the reference over the diagnostic window.

The per-spectrum hull is O(nbands); across a row-block it loops over pixels
(documented O(npix*nbands)). Restricting to a narrow window keeps this cheap.
Pure numpy — no numba/scipy dependency (optional acceleration noted only).
"""

from __future__ import annotations

import numpy as np


def _upper_hull_indices(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Indices (into x/y) of the upper convex hull, left-to-right.

    ``x`` must be strictly increasing. Monotone-chain Andrew's algorithm,
    keeping the upper boundary (the continuum over an absorption spectrum).
    """
    n = x.size
    if n <= 2:
        return np.arange(n)
    hull: list[int] = []
    for i in range(n):
        # For the UPPER hull we require clockwise turns (cross <= 0 pops).
        while len(hull) >= 2:
            o, a = hull[-2], hull[-1]
            cross = (x[a] - x[o]) * (y[i] - y[o]) - (y[a] - y[o]) * (x[i] - x[o])
            if cross >= 0:  # left turn or collinear -> a is below the hull
                hull.pop()
            else:
                break
        hull.append(i)
    return np.asarray(hull, dtype=np.intp)


def _continuum_removed_1d(wl: np.ndarray, vals: np.ndarray) -> np.ndarray:
    """Continuum-remove a single spectrum; NaN-safe, returns same shape."""
    out = np.full(vals.shape, np.nan, dtype=np.float64)
    finite = np.isfinite(wl) & np.isfinite(vals)
    if np.count_nonzero(finite) < 2:
        return out

    xf = wl[finite].astype(np.float64)
    yf = vals[finite].astype(np.float64)
    order = np.argsort(xf)
    xf = xf[order]
    yf = yf[order]

    hull_idx = _upper_hull_indices(xf, yf)
    hull_x = xf[hull_idx]
    hull_y = yf[hull_idx]

    # Hull interpolated back onto every finite band's wavelength.
    hull_on_bands = np.interp(wl[finite], hull_x, hull_y)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = vals[finite] / hull_on_bands
    # Guard against a zero / non-positive hull.
    ratio = np.where(np.isfinite(ratio) & (hull_on_bands > 0), ratio, np.nan)
    out[finite] = ratio
    return out


def continuum_removed(spectra: np.ndarray, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Continuum-remove a spectrum (1-D) or a stack of spectra (2-D).

    Parameters
    ----------
    spectra:
        Either ``(nbands,)`` or ``(npix, nbands)``.
    wavelengths_nm:
        ``(nbands,)`` wavelengths aligned with the last axis of ``spectra``.
    """
    wl = np.asarray(wavelengths_nm, dtype=np.float64).reshape(-1)
    arr = np.asarray(spectra, dtype=np.float64)

    if arr.ndim == 1:
        return _continuum_removed_1d(wl, arr)

    if arr.shape[1] != wl.size:
        raise ValueError(
            f"band mismatch: spectra have {arr.shape[1]} bands, wavelengths have {wl.size}"
        )
    out = np.empty_like(arr, dtype=np.float64)
    for i in range(arr.shape[0]):
        out[i] = _continuum_removed_1d(wl, arr[i])
    return out


def remove_reference_continuum(ref_vals: np.ndarray, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Convenience wrapper for a single reference spectrum."""
    return _continuum_removed_1d(
        np.asarray(wavelengths_nm, dtype=np.float64).reshape(-1),
        np.asarray(ref_vals, dtype=np.float64).reshape(-1),
    )
