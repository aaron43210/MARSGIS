"""End-to-end SAM run orchestration — the main Python API.

``run_sam`` is pure orchestration: it wires the readers, band selection,
resampling, optional continuum removal, the vectorized SAM core, and the COG /
provenance / report writers. All heavy lifting is delegated. Processing is
row-block chunked so only one band-plane of angles (not the whole cube) is held
in memory.

Contract (consumed by the backend):

    from marsgis_engine import run_sam, RunParams, SamResult
    result = run_sam(cube_path, reference_or_mineral, params)
    # result.angle_path, result.candidate_path,
    # result.provenance_path, result.report_path, result.stats

Outputs written into ``params.out_dir``:

* ``<prefix>_SAM_angle.tif``      COG float32, radians, NaN nodata
* ``<prefix>_SAM_candidate.tif``  COG uint8, {0, 1, 255}
* ``<prefix>_provenance.json``    conforms to schemas/provenance.schema.json
* ``<prefix>_report.txt``         human-readable summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from ..errors import WriteError
from ..io.envi_reader import load_cube, read_block
from ..io.provenance import build_provenance, write_provenance
from ..io.raster_writer import write_angle, write_candidate
from ..io.reference import load_reference
from ..io.report import write_report
from ..logging_utils import get_logger
from . import wavelengths as wl_mod
from .continuum import continuum_removed
from .resample import resample_reference
from .sam import sam_angles, threshold_mask

_log = get_logger("pipeline")


@dataclass
class RunParams:
    """Parameters for a single SAM run.

    ``threshold_rad`` is always in radians (the CLI converts ``--threshold-units
    deg`` before building this). Defaults mirror the frozen shared contract
    (contracts/enums.json -> defaults.sam).
    """

    threshold_rad: float = config.DEFAULT_THRESHOLD_RAD
    threshold_units: str = "rad"
    window_nm: tuple[float, float] = config.DEFAULT_WINDOW_NM
    mask_bad_bands: bool = config.DEFAULT_MASK_BAD_BANDS
    continuum_removal: bool = config.DEFAULT_CONTINUUM_REMOVAL
    resample_method: str = config.DEFAULT_RESAMPLE
    out_dir: str = "."
    out_prefix: str = config.DEFAULT_OUT_PREFIX
    crs_fallback_wkt: str | None = None
    timestamp: str | None = None
    block_rows: int = config.DEFAULT_BLOCK_ROWS
    engine_image: str = ""
    # Reference column overrides (passed through to load_reference).
    ref_wavelength_col: int = 0
    ref_value_col: int = 1
    ref_wavelength_units: str | None = None

    def __post_init__(self) -> None:
        self.threshold_rad = float(min(max(self.threshold_rad, 0.0), config.MAX_ANGLE_RAD))
        lo, hi = float(self.window_nm[0]), float(self.window_nm[1])
        self.window_nm = (min(lo, hi), max(lo, hi))
        if self.block_rows < 1:
            self.block_rows = config.DEFAULT_BLOCK_ROWS


@dataclass
class SamResult:
    """Paths + statistics for a completed SAM run."""

    angle_path: str
    candidate_path: str
    provenance_path: str
    report_path: str
    stats: dict[str, Any] = field(default_factory=dict)


def _build_alignment(
    cube: Any,
    reference: Any,
    window_mask: np.ndarray,
    ov_mask: np.ndarray,
    cand_idx: np.ndarray,
    final_idx: np.ndarray,
    wl_final: np.ndarray,
    params: Any,
) -> dict[str, Any]:
    """Per-stage band-drop ledger + the original/resampled wavelength grids.

    The funnel is internally consistent::

        n_bands_selected (window ∩ good)
          - n_bands_dropped_out_of_reference_coverage
          - n_bands_dropped_resample_nonfinite
          = n_bands_used

    so a reader can audit exactly which cube bands reached SAM and why the rest
    were dropped. The resampled grid (``bands_used_wavelengths_nm``) is recorded
    in full; the reference's own grid is pinned by its SHA-256 in ``inputs`` and
    summarised here by coverage so the record stays compact.
    """
    ref_wl = np.asarray(reference.wavelengths_nm, dtype=np.float64)
    n_selected = int(np.count_nonzero(window_mask))
    n_window_and_coverage = int(cand_idx.size)
    n_used = int(final_idx.size)
    return {
        "resample_method": str(params.resample_method),
        "cube_window_nm": [float(params.window_nm[0]), float(params.window_nm[1])],
        "reference_coverage_nm": [
            float(np.nanmin(ref_wl)) if ref_wl.size else None,
            float(np.nanmax(ref_wl)) if ref_wl.size else None,
        ],
        "n_reference_points": int(reference.point_count),
        "n_bands_total": int(cube.bands),
        "n_bands_in_reference_coverage": int(np.count_nonzero(ov_mask)),
        "n_bands_selected": n_selected,
        "n_bands_window_and_coverage": n_window_and_coverage,
        "n_bands_dropped_out_of_reference_coverage": n_selected - n_window_and_coverage,
        "n_bands_dropped_resample_nonfinite": n_window_and_coverage - n_used,
        "n_bands_used": n_used,
        "bands_used_wavelengths_nm": [round(float(w), 3) for w in np.asarray(wl_final).ravel()],
    }


def _native_bounds(cube: Any) -> list[float] | None:
    """(west, south, east, north) in the raster's own CRS units."""
    try:
        from rasterio.transform import array_bounds

        w, s, e, n = array_bounds(cube.rows, cube.cols, cube.transform)
        return [float(w), float(s), float(e), float(n)]
    except Exception:  # noqa: BLE001
        return None


def _compute_stats(angle: np.ndarray, mask: np.ndarray, threshold_rad: float) -> dict[str, Any]:
    finite = np.isfinite(angle)
    valid_vals = angle[finite]
    detected = mask == config.CANDIDATE_MATCH
    cand_vals = angle[detected & finite]

    n_pixels = int(angle.size)
    n_valid = int(valid_vals.size)
    n_detected = int(np.count_nonzero(detected))

    def _f(fn, arr):
        return float(fn(arr)) if arr.size else None

    stats: dict[str, Any] = {
        "pixel_count": n_pixels,
        "valid_pixel_count": n_valid,
        "detected_pixel_count": n_detected,
        "detected_fraction": (n_detected / n_valid) if n_valid else 0.0,
        "min": _f(np.min, valid_vals),
        "max": _f(np.max, valid_vals),
        "mean": _f(np.mean, valid_vals),
        "median": _f(np.median, valid_vals),
        "std": _f(np.std, valid_vals),
        "candidate_angle_min": _f(np.min, cand_vals),
        "candidate_angle_median": _f(np.median, cand_vals),
        "threshold_rad": float(threshold_rad),
        "value_range": [
            _f(np.min, valid_vals) if n_valid else 0.0,
            _f(np.max, valid_vals) if n_valid else float(threshold_rad),
        ],
    }
    return stats


def run_sam(cube_path: str, reference_or_mineral: str, params: RunParams) -> SamResult:
    """Run SAM on ``cube_path`` against ``reference_or_mineral``.

    ``reference_or_mineral`` is either a bundled mineral alias (``carbonate``,
    ``olivine``, ``clay``) resolved via data/minerals.json, or a path to a MICA
    ``.tab`` / CSV reference.
    """
    out_dir = Path(params.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = params.out_prefix

    _log.info("loading cube %s", cube_path)
    cube = load_cube(cube_path, crs_fallback_wkt=params.crs_fallback_wkt)
    _log.info(
        "cube %s shape=%s bands=%d good=%d crs_fallback=%s",
        cube.label_id,
        cube.shape,
        cube.bands,
        cube.n_good_bands,
        cube.crs_is_fallback,
    )

    _log.info("loading reference %s", reference_or_mineral)
    reference = load_reference(
        reference_or_mineral,
        wavelength_col=params.ref_wavelength_col,
        value_col=params.ref_value_col,
        wavelength_units=params.ref_wavelength_units,
    )

    # --- Band selection -------------------------------------------------
    window_mask = wl_mod.select_bands(
        cube.wavelengths_nm, cube.bbl, params.window_nm, mask_bad_bands=params.mask_bad_bands
    )
    ov_mask = wl_mod.overlap_mask(cube.wavelengths_nm, reference.wavelengths_nm)
    cand_mask = window_mask & ov_mask
    cand_idx = np.where(cand_mask)[0]
    if cand_idx.size == 0:
        wl_mod.require_overlap(cand_mask, context="window ∩ reference coverage")

    sel_wl = cube.wavelengths_nm[cand_idx]
    ref_resampled, valid = resample_reference(
        reference.wavelengths_nm,
        reference.values,
        sel_wl,
        method=params.resample_method,
        target_fwhm_nm=(cube.fwhm_nm[cand_idx] if cube.fwhm_nm is not None else None),
        ref_fwhm_nm=None,
    )
    final_idx = cand_idx[valid]
    final_mask = np.zeros(cube.bands, dtype=bool)
    final_mask[final_idx] = True
    n_used = wl_mod.require_overlap(final_mask, context="finite resampled reference bands")

    wl_final = cube.wavelengths_nm[final_idx]
    ref_vec = ref_resampled[valid]

    # Auditable band-alignment ledger: how the cube's bands funnel down to the
    # set actually fed to SAM. Recorded in provenance so a reader can see which
    # bands were used and why the others were dropped (A4 honesty requirement).
    alignment = _build_alignment(
        cube, reference, window_mask, ov_mask, cand_idx, final_idx, wl_final, params
    )

    if params.continuum_removal:
        ref_used = continuum_removed(ref_vec, wl_final)
    else:
        ref_used = ref_vec
    ref_used = np.asarray(ref_used, dtype=np.float64)

    _log.info(
        "SAM over %d bands (window %s nm, continuum=%s, resample=%s)",
        n_used,
        params.window_nm,
        params.continuum_removal,
        params.resample_method,
    )

    # --- Row-block SAM --------------------------------------------------
    angle = np.full((cube.rows, cube.cols), np.nan, dtype=np.float32)
    step = int(params.block_rows)
    for r0 in range(0, cube.rows, step):
        r1 = min(cube.rows, r0 + step)
        block = read_block(cube, r0, r1)  # (rows, cols, bands) float32, NaN missing
        sub = block[:, :, final_idx]  # (rows, cols, K)
        rb, cb, kb = sub.shape
        flat = sub.reshape(rb * cb, kb).astype(np.float64)
        if params.continuum_removal:
            flat = continuum_removed(flat, wl_final)
        block_angles = sam_angles(flat, ref_used)
        angle[r0:r1, :] = block_angles.reshape(rb, cb).astype(np.float32)

    mask = threshold_mask(angle, params.threshold_rad)

    # --- Statistics -----------------------------------------------------
    stats = _compute_stats(angle, mask, params.threshold_rad)
    band_counts = wl_mod.band_summary(window_mask, cube.bbl, final_mask)
    stats.update(band_counts)
    stats["mineral"] = reference.mineral_key
    stats["reference"] = reference.name
    stats["width"] = int(cube.cols)
    stats["height"] = int(cube.rows)
    stats["crs_is_fallback"] = bool(cube.crs_is_fallback)
    stats["crs"] = _crs_text(cube.crs)
    stats["bounds_native"] = _native_bounds(cube)
    stats["bounds_crs_units"] = "CRS units (metres for the Mars equirectangular grid)"
    stats["caveat"] = config.CANDIDATE_DISCLAIMER

    # --- Write rasters --------------------------------------------------
    angle_path = out_dir / f"{prefix}{config.ANGLE_SUFFIX}"
    candidate_path = out_dir / f"{prefix}{config.CANDIDATE_SUFFIX}"
    provenance_path = out_dir / f"{prefix}{config.PROVENANCE_SUFFIX}"
    report_path = out_dir / f"{prefix}{config.REPORT_SUFFIX}"

    raster_tags = {
        "MINERAL": reference.mineral_key,
        "REFERENCE": reference.name,
        "THRESHOLD_RAD": f"{params.threshold_rad:.6f}",
        "CONTINUUM_REMOVAL": str(params.continuum_removal),
    }
    _log.info("writing angle COG %s", angle_path.name)
    write_angle(angle_path, angle, cube, tags=raster_tags)
    _log.info("writing candidate COG %s", candidate_path.name)
    write_candidate(candidate_path, mask, cube, tags=raster_tags)

    # --- Provenance + report (checksums of the written rasters) ---------
    record = build_provenance(
        cube,
        reference,
        params,
        stats,
        timestamp=params.timestamp,
        output_paths={"angle": angle_path, "candidate": candidate_path},
        engine_image=params.engine_image,
        alignment=alignment,
    )
    write_provenance(provenance_path, record)
    write_report(report_path, record)

    if not (angle_path.exists() and candidate_path.exists()):  # pragma: no cover
        raise WriteError("expected output rasters were not created")

    _log.info(
        "done: %d candidate px / %d valid (%.3f%%)",
        stats["detected_pixel_count"],
        stats["valid_pixel_count"],
        (stats["detected_fraction"] * 100.0),
    )

    return SamResult(
        angle_path=str(angle_path),
        candidate_path=str(candidate_path),
        provenance_path=str(provenance_path),
        report_path=str(report_path),
        stats=stats,
    )


def _crs_text(crs: Any) -> str:
    if crs is None:
        return ""
    for attr in ("to_wkt", "wkt"):
        try:
            val = getattr(crs, attr)
            return val() if callable(val) else str(val)
        except Exception:  # noqa: BLE001
            continue
    return str(crs)
