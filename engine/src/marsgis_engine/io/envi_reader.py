"""Dual-reader for a CRISM MTRDR ENVI cube.

Two libraries, two concerns:

* **spectral (SPy)** parses the ENVI *spectral* metadata that GDAL exposes
  weakly — per-band wavelengths (``bands.centers``), the bad-band list
  (``bbl``), FWHM, wavelength units, and the data-ignore value — and provides
  the windowed spectral reads.
* **rasterio / GDAL** parses the ENVI ``map info`` / coordinate-system-string
  into a proper affine ``transform`` + ``crs``.

All wavelengths are normalised to nanometres internally.

This module performs NO radiometric re-calibration and NO reprojection: CRISM
MTRDR is analysis-ready I/F and its grid is preserved. If GDAL cannot resolve
the Mars datum, a configurable Mars-2000 equirectangular fallback WKT is
attached and the assumption is logged + recorded (``crs_is_fallback``); a
CRS-less raster is never produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from ..errors import CubeReadError, HeaderParseError
from ..logging_utils import get_logger, log_assumption
from ..science.wavelengths import to_nm, unit_scale_to_nm

_log = get_logger("envi_reader")


@dataclass
class CrismCube:
    """An opened, analysis-ready CRISM MTRDR cube (lazy pixel access)."""

    path: Path
    hdr_path: Path
    rows: int
    cols: int
    bands: int
    wavelengths_nm: np.ndarray
    bbl: np.ndarray | None  # bool, True == good band; None if absent
    fwhm_nm: np.ndarray | None
    ignore_value: float | None
    transform: Any  # affine.Affine
    crs: Any  # rasterio.crs.CRS | None
    crs_is_fallback: bool
    interleave: str
    label_id: str
    wavelength_units: str
    metadata: dict[str, Any] = field(default_factory=dict)
    _spy_image: Any = None  # cached SPy SpyFile handle

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.rows, self.cols, self.bands)

    @property
    def n_good_bands(self) -> int:
        if self.bbl is None:
            return self.bands
        return int(np.count_nonzero(self.bbl))


def resolve_pair(path: str | Path) -> tuple[Path, Path]:
    """Given a .hdr or .img (or bare stem) path, return ``(hdr, img)``.

    Raises :class:`CubeReadError` when neither member can be located.
    """
    p = Path(path)
    stem = p.with_suffix("")
    candidates_img = [
        p.with_suffix(".img"),
        stem.with_suffix(".img"),
        p.with_suffix(".dat"),
        stem.with_suffix(".dat"),
    ]
    candidates_hdr = [p.with_suffix(".hdr"), stem.with_suffix(".hdr")]

    if p.suffix.lower() == ".hdr":
        hdr = p
    else:
        hdr = next((c for c in candidates_hdr if c.exists()), p.with_suffix(".hdr"))

    if p.suffix.lower() in (".img", ".dat"):
        img = p
    else:
        img = next((c for c in candidates_img if c.exists()), p.with_suffix(".img"))

    if not hdr.exists():
        raise CubeReadError(
            f"ENVI header not found for {path!s}",
            hint="pass the .hdr or .img path; the .hdr must sit beside the .img",
        )
    if not img.exists():
        raise CubeReadError(
            f"ENVI data file not found for {path!s}",
            hint="the raw .img/.dat must sit beside the .hdr",
        )
    return hdr, img


def _as_bool_bbl(raw: Any, nbands: int) -> np.ndarray | None:
    """Normalise an ENVI 'bbl' metadata value to a bool good-band mask."""
    if raw is None:
        return None
    try:
        vals = [float(x) for x in raw]
    except (TypeError, ValueError):
        return None
    if len(vals) != nbands:
        _log.warning("bbl length %d != bands %d; ignoring bbl", len(vals), nbands)
        return None
    # ENVI convention: 1 == good band, 0 == bad band.
    return np.asarray(vals, dtype=np.float64) > 0.5


def _parse_map_info(map_info: Any) -> tuple[float, float, float, float, float, float] | None:
    """Parse an ENVI 'map info' into (ref_px, ref_py, east, north, xsize, ysize).

    Returns None if the structure is not understood.
    """
    if map_info is None:
        return None
    if isinstance(map_info, str):
        parts = [t.strip() for t in map_info.strip("{}").split(",")]
    else:
        parts = [str(t).strip() for t in map_info]
    nums: list[float] = []
    for tok in parts[1:7] if len(parts) >= 7 else []:
        try:
            nums.append(float(tok))
        except ValueError:
            return None
    if len(nums) < 6:
        return None
    ref_px, ref_py, east, north, xsize, ysize = nums[:6]
    return ref_px, ref_py, east, north, xsize, ysize


def _transform_from_map_info(map_info: Any):
    """Build an affine.Affine from an ENVI 'map info' tie point."""
    from affine import Affine

    parsed = _parse_map_info(map_info)
    if parsed is None:
        return None
    ref_px, ref_py, east, north, xsize, ysize = parsed
    # ENVI tie point (ref_px, ref_py) is 1-based and refers to the UL corner of
    # that pixel in the common MTRDR convention; translate to the UL corner of
    # the image (pixel 1,1).
    ulx = east - (ref_px - 1.0) * xsize
    uly = north + (ref_py - 1.0) * ysize
    return Affine(xsize, 0.0, ulx, 0.0, -ysize, uly)


def _parse_label_id(img: Path, metadata: dict[str, Any]) -> str:
    """Best-effort observation / product id for provenance."""
    # Prefer a sibling PDS label if present.
    for ext in (".xml", ".lbl", ".LBL", ".XML"):
        sib = img.with_suffix(ext)
        if sib.exists():
            try:
                text = sib.read_text(errors="ignore")
            except OSError:
                continue
            m = re.search(r"(?:PRODUCT_ID|SOURCE_PRODUCT_ID)\s*=\s*\"?([A-Za-z0-9_]+)", text)
            if m:
                return m.group(1)
    desc = metadata.get("description")
    if isinstance(desc, str):
        m = re.search(r"(frt[0-9a-fA-F]+_\w+)", desc)
        if m:
            return m.group(1)
    return img.stem


def load_cube(path: str | Path, *, crs_fallback_wkt: str | None = None) -> CrismCube:
    """Open a CRISM MTRDR ENVI cube and read its header metadata.

    Pixel data is NOT loaded here; use :func:`read_block` for windowed reads.
    """
    try:
        import spectral.io.envi as envi  # type: ignore
    except Exception as exc:  # pragma: no cover - spectral present in CI
        raise CubeReadError(f"the 'spectral' package is required: {exc}") from exc

    hdr, img = resolve_pair(path)

    try:
        spy = envi.open(str(hdr), image=str(img))
    except Exception as exc:
        raise HeaderParseError(
            f"could not parse ENVI header {hdr.name}: {exc}",
            hint="verify the .hdr is a valid ENVI header matching the .img",
        ) from exc

    meta = dict(getattr(spy, "metadata", {}) or {})
    rows = int(spy.shape[0])
    cols = int(spy.shape[1])
    bands = int(spy.shape[2])

    wl_units = str(meta.get("wavelength units") or meta.get("wavelength_units") or "")
    centers = getattr(spy.bands, "centers", None)
    if centers is None or len(centers) == 0:
        raise HeaderParseError(
            f"ENVI header {hdr.name} declares no per-band wavelengths",
            hint="SAM needs the 'wavelength' array in the .hdr",
        )
    if len(centers) != bands:
        # Mismatch -> silent band/wavelength misalignment (wrong science) or a
        # later IndexError. Reject early with a clear message.
        raise HeaderParseError(
            f"ENVI header {hdr.name} declares {bands} bands but lists {len(centers)} wavelengths",
            hint="the band count and the 'wavelength' array length must match",
        )
    wavelengths_nm = to_nm(np.asarray(centers, dtype=np.float64), wl_units or "nm")

    fwhm_raw = getattr(spy.bands, "bandwidths", None) or meta.get("fwhm")
    fwhm_nm = None
    if fwhm_raw is not None and len(fwhm_raw) == bands:
        fwhm_nm = np.asarray(fwhm_raw, dtype=np.float64) * unit_scale_to_nm(wl_units or "nm")

    bbl = _as_bool_bbl(meta.get("bbl"), bands)

    ignore_raw = meta.get("data ignore value", meta.get("data_ignore_value"))
    ignore_value: float | None
    if ignore_raw is None:
        ignore_value = None
    else:
        try:
            ignore_value = float(ignore_raw)
        except (TypeError, ValueError):
            ignore_value = None

    interleave = str(meta.get("interleave", "bsq")).lower()

    # --- CRS + transform via rasterio/GDAL -------------------------------
    transform = None
    crs = None
    try:
        import rasterio  # type: ignore

        with rasterio.open(str(img)) as ds:
            transform = ds.transform
            crs = ds.crs
    except Exception as exc:  # noqa: BLE001 - fall back to header-derived geo
        _log.warning("rasterio could not read geotransform from %s (%s)", img.name, exc)

    from affine import Affine

    if transform is None or transform == Affine.identity():
        hdr_transform = _transform_from_map_info(meta.get("map info"))
        if hdr_transform is not None:
            transform = hdr_transform
            log_assumption(_log, f"affine derived from ENVI 'map info' for {img.name}")
        else:
            transform = Affine.identity()
            log_assumption(_log, f"no geotransform resolvable for {img.name}; using identity")

    crs_is_fallback = False
    if crs is None:
        fallback = crs_fallback_wkt or config.MARS2000_EQUIRECT_WKT
        crs = fallback
        try:
            from rasterio.crs import CRS as RioCRS  # type: ignore

            try:
                crs = RioCRS.from_wkt(fallback)
            except Exception:  # noqa: BLE001 - may be an authority code, not WKT
                crs = RioCRS.from_user_input(fallback)
        except Exception:  # pragma: no cover - rasterio present in CI
            crs = fallback
        crs_is_fallback = True
        log_assumption(
            _log,
            f"no CRS resolved from ENVI header for {img.name}; attaching Mars-2000 "
            "equirectangular fallback (verify with 'marsgis-engine info')",
        )

    label_id = _parse_label_id(img, meta)

    return CrismCube(
        path=img,
        hdr_path=hdr,
        rows=rows,
        cols=cols,
        bands=bands,
        wavelengths_nm=wavelengths_nm,
        bbl=bbl,
        fwhm_nm=fwhm_nm,
        ignore_value=ignore_value,
        transform=transform,
        crs=crs,
        crs_is_fallback=crs_is_fallback,
        interleave=interleave,
        label_id=label_id,
        wavelength_units=wl_units or "nm",
        metadata=meta,
        _spy_image=spy,
    )


def read_block(cube: CrismCube, row_start: int, row_stop: int) -> np.ndarray:
    """Read rows ``[row_start, row_stop)`` as a float32 ``(rows, cols, bands)``.

    The data-ignore value and any non-finite samples are converted to NaN so
    downstream SAM / continuum code can treat them uniformly as missing.
    """
    row_start = max(0, int(row_start))
    row_stop = min(cube.rows, int(row_stop))
    if row_stop <= row_start:
        return np.empty((0, cube.cols, cube.bands), dtype=np.float32)

    spy = cube._spy_image
    if spy is None:  # pragma: no cover - reopened defensively
        import spectral.io.envi as envi  # type: ignore

        spy = envi.open(str(cube.hdr_path), image=str(cube.path))
        cube._spy_image = spy

    block = np.asarray(
        spy.read_subregion((row_start, row_stop), (0, cube.cols)),
        dtype=np.float32,
    )
    if block.ndim == 2:  # single band edge case
        block = block[:, :, np.newaxis]

    if cube.ignore_value is not None:
        block[block == np.float32(cube.ignore_value)] = np.nan
    block[~np.isfinite(block)] = np.nan
    return block
