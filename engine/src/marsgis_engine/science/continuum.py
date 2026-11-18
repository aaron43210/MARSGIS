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
    # Fully finite rows on a strictly increasing grid (almost every pixel) take the
    # vectorised path; rows with gaps keep the per-pixel path. Both give identical results.
    fast = np.all(np.isfinite(arr), axis=1)
    if wl.size < 2 or not np.all(np.isfinite(wl)) or not np.all(np.diff(wl) > 0):
        fast[:] = False
    if fast.any():
        out[fast] = _continuum_removed_rows(wl, arr[fast])
    for i in np.flatnonzero(~fast):
        out[i] = _continuum_removed_1d(wl, arr[i])
    return out


def _continuum_removed_rows(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Continuum removal of many fully finite spectra at once.

    The same monotone-chain upper hull and linear interpolation as
    :func:`_continuum_removed_1d`, run for every row in lock-step with numpy
    instead of a Python loop per pixel. ``x`` must be strictly increasing.
    """
    m, n = y.shape
    rows = np.arange(m)
    stack = np.empty((m, n), dtype=np.intp)  # per-row hull stack of band indices
    top = np.zeros(m, dtype=np.intp)  # stack size per row
    for i in range(n):
        cand = np.flatnonzero(top >= 2)
        while cand.size:
            o = stack[cand, top[cand] - 2]
            a = stack[cand, top[cand] - 1]
            cross = (x[a] - x[o]) * (y[cand, i] - y[cand, o]) - (y[cand, a] - y[cand, o]) * (
                x[i] - x[o]
            )
            pop = cand[cross >= 0]  # left turn or collinear: a is below the hull
            top[pop] -= 1
            cand = pop[top[pop] >= 2]  # only rows that just popped can pop again
        stack[rows, top] = i
        top += 1

    on_hull = np.zeros((m, n), dtype=bool)
    on_hull[np.repeat(rows, top), stack[np.arange(n) < top[:, None]]] = True

    # Nearest hull vertex at or left / at or right of every band (first and last
    # band are always on the hull).
    idx = np.broadcast_to(np.arange(n), (m, n))
    left = np.maximum.accumulate(np.where(on_hull, idx, -1), axis=1)
    right = np.minimum.accumulate(np.where(on_hull, idx, n)[:, ::-1], axis=1)[:, ::-1]
    yl = np.take_along_axis(y, left, axis=1)
    yr = np.take_along_axis(y, right, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (yr - yl) / (x[right] - x[left])
        hull = np.where(left == right, yl, slope * (x - x[left]) + yl)  # numpy.interp's formula
        ratio = y / hull
    return np.where(np.isfinite(ratio) & (hull > 0), ratio, np.nan)


def remove_reference_continuum(ref_vals: np.ndarray, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Convenience wrapper for a single reference spectrum."""
    return _continuum_removed_1d(
        np.asarray(wavelengths_nm, dtype=np.float64).reshape(-1),
        np.asarray(ref_vals, dtype=np.float64).reshape(-1),
    )
