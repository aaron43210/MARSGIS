"""Resample a reference spectrum onto the cube's wavelength grid.

The reference (MICA .tab) and the cube rarely share a wavelength grid, so the
reference must be interpolated onto the cube's selected bands before SAM. Two
methods:

* ``linear``   : :func:`numpy.interp` with out-of-range bands marked NaN. Robust
  and dependency-light; the default.
* ``gaussian`` : FWHM-aware band-response resampling via
  :class:`spectral.BandResampler` when the cube's per-band FWHM is known. Falls
  back to linear (with a logged warning) when FWHM is unavailable.

Output is always aligned 1:1 with the target band grid; a companion boolean
``valid`` mask marks the finite (in-coverage) bands.
"""

from __future__ import annotations

import numpy as np

from ..logging_utils import get_logger

_log = get_logger("resample")


def resample_reference(
    ref_wl_nm: np.ndarray,
    ref_vals: np.ndarray,
    target_wl_nm: np.ndarray,
    *,
    method: str = "linear",
    target_fwhm_nm: np.ndarray | None = None,
    ref_fwhm_nm: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Resample ``ref_vals`` from ``ref_wl_nm`` onto ``target_wl_nm``.

    Returns ``(resampled_values, valid_mask)`` both shaped like
    ``target_wl_nm``. ``valid_mask`` is True where the resampled value is finite
    and the target wavelength lies within the reference coverage.
    """
    ref_wl = np.asarray(ref_wl_nm, dtype=np.float64)
    ref_v = np.asarray(ref_vals, dtype=np.float64)
    target = np.asarray(target_wl_nm, dtype=np.float64)

    # Keep only finite, strictly increasing reference samples.
    good = np.isfinite(ref_wl) & np.isfinite(ref_v)
    ref_wl = ref_wl[good]
    ref_v = ref_v[good]
    order = np.argsort(ref_wl)
    ref_wl = ref_wl[order]
    ref_v = ref_v[order]

    method = (method or "linear").lower()
    if method == "gaussian":
        resampled = _resample_gaussian(ref_wl, ref_v, target, target_fwhm_nm, ref_fwhm_nm)
        if resampled is None:
            resampled = _resample_linear(ref_wl, ref_v, target)
    elif method == "linear":
        resampled = _resample_linear(ref_wl, ref_v, target)
    else:
        raise ValueError(f"unknown resample method: {method!r}")

    valid = np.isfinite(resampled)
    return resampled, valid


def _resample_linear(ref_wl: np.ndarray, ref_v: np.ndarray, target: np.ndarray) -> np.ndarray:
    """numpy.interp with NaN outside the reference coverage."""
    if ref_wl.size < 2:
        return np.full(target.shape, np.nan, dtype=np.float64)
    out = np.interp(target, ref_wl, ref_v, left=np.nan, right=np.nan)
    # np.interp returns the edge value for exact-boundary targets; keep those,
    # but anything strictly outside already became NaN via left/right.
    return out.astype(np.float64)


def _resample_gaussian(
    ref_wl: np.ndarray,
    ref_v: np.ndarray,
    target: np.ndarray,
    target_fwhm_nm: np.ndarray | None,
    ref_fwhm_nm: np.ndarray | None,
) -> np.ndarray | None:
    """FWHM-aware resampling via spectral.BandResampler; None -> fall back."""
    if target_fwhm_nm is None:
        _log.warning(
            "ASSUMED: gaussian resample requested but cube FWHM is unknown; "
            "falling back to linear interpolation"
        )
        return None
    try:
        from spectral import BandResampler  # type: ignore
    except Exception as exc:  # pragma: no cover - spectral always installed in CI
        _log.warning("spectral.BandResampler unavailable (%s); falling back to linear", exc)
        return None

    tgt_fwhm = np.asarray(target_fwhm_nm, dtype=np.float64)
    if ref_fwhm_nm is not None:
        resampler = BandResampler(
            ref_wl, target, np.asarray(ref_fwhm_nm, dtype=np.float64), tgt_fwhm
        )
    else:
        resampler = BandResampler(ref_wl, target, None, tgt_fwhm)
    out = np.asarray(resampler(ref_v), dtype=np.float64)
    # BandResampler marks out-of-range bands NaN already; ensure dtype/shape.
    return out.reshape(target.shape)
