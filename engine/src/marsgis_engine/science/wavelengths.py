"""Wavelength unit normalization and good-band selection.

All wavelengths inside the engine are nanometres. CRISM .hdr files declare
``wavelength units = Micrometers`` (um) while some products use nm; MICA .tab
columns are um. Converting everything to a single internal unit removes a whole
class of off-by-1000 bugs.
"""

from __future__ import annotations

import numpy as np

from .. import config
from ..errors import WavelengthOverlapError
from ..logging_utils import get_logger

_log = get_logger("wavelengths")

# Recognised ENVI 'wavelength units' spellings -> nanometre scale factor.
_UNIT_SCALE_TO_NM: dict[str, float] = {
    "nm": 1.0,
    "nanometers": 1.0,
    "nanometres": 1.0,
    "nanometer": 1.0,
    "um": 1000.0,
    "micrometers": 1000.0,
    "micrometres": 1000.0,
    "micrometer": 1000.0,
    "micron": 1000.0,
    "microns": 1000.0,
}


def unit_scale_to_nm(units: str | None) -> float:
    """Return the multiplicative factor converting ``units`` to nanometres.

    Falls back to 1.0 (assume nm) with a logged assumption when ``units`` is
    unknown or absent.
    """
    if not units:
        _log.warning("ASSUMED: no wavelength units given; assuming nanometres")
        return 1.0
    key = str(units).strip().lower()
    scale = _UNIT_SCALE_TO_NM.get(key)
    if scale is None:
        _log.warning("ASSUMED: unrecognised wavelength units %r; assuming nanometres", units)
        return 1.0
    return scale


def to_nm(values: np.ndarray | list[float], units: str | None) -> np.ndarray:
    """Convert an array of wavelength ``values`` in ``units`` to nanometres."""
    arr = np.asarray(values, dtype=np.float64)
    return arr * unit_scale_to_nm(units)


def select_bands(
    wavelengths_nm: np.ndarray,
    bbl: np.ndarray | None,
    window_nm: tuple[float, float],
    *,
    mask_bad_bands: bool = True,
) -> np.ndarray:
    """Boolean mask of cube bands to use.

    Combines (a) membership in the diagnostic wavelength ``window_nm`` with
    (b) the ENVI bad-band list ``bbl`` (True == good) when ``mask_bad_bands``
    is enabled and a bbl is available.
    """
    wl = np.asarray(wavelengths_nm, dtype=np.float64)
    lo, hi = float(window_nm[0]), float(window_nm[1])
    if lo > hi:
        lo, hi = hi, lo
    mask = (wl >= lo) & (wl <= hi) & np.isfinite(wl)

    if mask_bad_bands and bbl is not None:
        good = np.asarray(bbl, dtype=bool)
        if good.shape == mask.shape:
            mask &= good
        else:  # pragma: no cover - defensive; shapes validated upstream
            _log.warning(
                "bbl length %d != band count %d; ignoring bbl",
                good.size,
                mask.size,
            )
    return mask


def overlap_mask(cube_wl_nm: np.ndarray, ref_wl_nm: np.ndarray) -> np.ndarray:
    """Boolean mask of cube bands lying within the reference's coverage."""
    cube_wl = np.asarray(cube_wl_nm, dtype=np.float64)
    ref_wl = np.asarray(ref_wl_nm, dtype=np.float64)
    ref_lo = float(np.nanmin(ref_wl))
    ref_hi = float(np.nanmax(ref_wl))
    return (cube_wl >= ref_lo) & (cube_wl <= ref_hi) & np.isfinite(cube_wl)


def require_overlap(mask: np.ndarray, *, context: str = "") -> int:
    """Return the number of selected bands, raising if below the minimum.

    Raises :class:`WavelengthOverlapError` when fewer than
    ``config.MIN_OVERLAP_BANDS`` bands survive, rather than silently matching
    on a degenerate band set.
    """
    n = int(np.count_nonzero(mask))
    if n < config.MIN_OVERLAP_BANDS:
        suffix = f" ({context})" if context else ""
        raise WavelengthOverlapError(
            f"only {n} usable overlapping bands{suffix}; need at least {config.MIN_OVERLAP_BANDS}",
            hint="widen --wmin/--wmax, disable --mask-bad-bands, or check that "
            "the reference and cube wavelength ranges overlap",
        )
    return n


def band_summary(
    window_mask: np.ndarray,
    bbl: np.ndarray | None,
    final_mask: np.ndarray,
) -> dict[str, int]:
    """Counts for the report / provenance record."""
    total = int(final_mask.size)
    n_bad = 0 if bbl is None else int(np.count_nonzero(~np.asarray(bbl, dtype=bool)))
    return {
        "n_bands_total": total,
        "n_bands_in_window": int(np.count_nonzero(window_mask)),
        "n_bad_bands": n_bad,
        "n_bands_used": int(np.count_nonzero(final_mask)),
    }
