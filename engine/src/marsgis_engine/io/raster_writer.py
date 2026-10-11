"""Write the angle + candidate rasters as validated Cloud-Optimized GeoTIFFs.

GDAL's COG driver is effectively single-pass CreateCopy, which conflicts with
chunked windowed writes. So the strategy is: write a tiled interim GTiff, then
``rasterio.shutil.copy(..., driver="COG")`` to produce a true, overview-bearing
COG (the COG driver builds overviews itself via OVERVIEWS=AUTO). The input
CRS + affine are preserved exactly (or the logged Mars-2000 fallback); a
CRS-less raster is never emitted.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from .._version import __version__
from ..errors import WriteError
from ..logging_utils import get_logger

_log = get_logger("raster_writer")

#: Interim-GTiff internal tile size (must be a multiple of 16 for tiled TIFF).
_INTERIM_BLOCK = 256


def _cog_creation_options(dtype: str) -> dict[str, Any]:
    """COG-driver creation options, with a dtype-appropriate predictor."""
    predictor = 3 if np.dtype(dtype).kind == "f" else 2
    return {
        "COMPRESS": str(config.COG_PROFILE["compress"]),
        "PREDICTOR": predictor,
        "BLOCKSIZE": int(config.COG_PROFILE["blocksize"]),
        "OVERVIEW_RESAMPLING": str(config.COG_PROFILE["overview_resampling"]),
        "BIGTIFF": str(config.COG_PROFILE["bigtiff"]),
    }


def write_cog(
    path: str | Path,
    array: np.ndarray,
    *,
    transform: Any,
    crs: Any,
    dtype: str,
    nodata: float | None,
    band_description: str = "",
    tags: dict[str, Any] | None = None,
    color_interp: str | None = None,
    category_names: list[str] | None = None,
) -> Path:
    """Write ``array`` (2-D, single band) as a COG at ``path``.

    Returns the output path. Raises :class:`WriteError` on any failure.
    """
    try:
        import rasterio
        from rasterio.enums import ColorInterp
        from rasterio.shutil import copy as rio_copy
    except Exception as exc:  # pragma: no cover - rasterio present in CI
        raise WriteError(f"the 'rasterio' package is required to write COGs: {exc}") from exc

    path = Path(path)
    arr = np.asarray(array)
    if arr.ndim != 2:
        raise WriteError(f"expected a 2-D array, got shape {arr.shape}")
    arr = np.ascontiguousarray(arr, dtype=dtype)
    height, width = arr.shape

    if crs is None:  # defensive: pipeline guarantees a CRS, never emit CRS-less
        raise WriteError("refusing to write a CRS-less raster; attach a Mars CRS first")

    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".tif", prefix="marsgis_", dir=str(path.parent))
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)

    try:
        gtiff_profile: dict[str, Any] = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": 1,
            "dtype": dtype,
            "crs": crs,
            "transform": transform,
            "tiled": True,
            "blockxsize": _INTERIM_BLOCK,
            "blockysize": _INTERIM_BLOCK,
            "compress": "DEFLATE",
        }
        if nodata is not None:
            gtiff_profile["nodata"] = nodata

        with rasterio.open(tmp_path, "w", **gtiff_profile) as dst:
            dst.write(arr, 1)
            if band_description:
                dst.set_band_description(1, band_description)
            if color_interp is not None:
                try:
                    dst.colorinterp = [getattr(ColorInterp, color_interp)]
                except Exception:  # noqa: BLE001
                    pass
            stamp = {"SOFTWARE": f"marsgis-engine {__version__}", "ALGORITHM": "SAM"}
            if tags:
                stamp.update({k: str(v) for k, v in tags.items()})
            dst.update_tags(**stamp)
            if category_names is not None:
                dst.update_tags(1, CATEGORY_NAMES=",".join(category_names))

        cog_opts = _cog_creation_options(dtype)
        rio_copy(str(tmp_path), str(path), driver="COG", **cog_opts)
    except WriteError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WriteError(f"failed to write COG {path.name}: {exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass

    return path


def write_angle(
    path: str | Path,
    angle_f32: np.ndarray,
    cube: Any,
    *,
    tags: dict[str, Any] | None = None,
) -> Path:
    """Write the float32 SAM angle raster (radians, NaN nodata)."""
    extra = {"UNITS": "radians", "METRIC": "SAM_spectral_angle"}
    if tags:
        extra.update(tags)
    return write_cog(
        path,
        angle_f32.astype(np.float32),
        transform=cube.transform,
        crs=cube.crs,
        dtype="float32",
        nodata=config.ANGLE_NODATA,
        band_description="SAM spectral angle (radians); lower = closer match",
        tags=extra,
        color_interp="gray",
    )


def write_candidate(
    path: str | Path,
    mask_u8: np.ndarray,
    cube: Any,
    *,
    tags: dict[str, Any] | None = None,
) -> Path:
    """Write the uint8 candidate mask (0 non-match, 1 candidate, 255 nodata)."""
    extra = {
        "UNITS": "class",
        "CLASS_0": "non_match",
        "CLASS_1": "candidate_match",
        "NODATA": "255",
        "CAVEAT": config.CANDIDATE_DISCLAIMER,
    }
    if tags:
        extra.update(tags)
    return write_cog(
        path,
        mask_u8.astype(np.uint8),
        transform=cube.transform,
        crs=cube.crs,
        dtype="uint8",
        nodata=float(config.CANDIDATE_NODATA),
        band_description="SAM candidate match (1=candidate, 0=non-match, 255=nodata)",
        tags=extra,
        color_interp="gray",
        category_names=["non_match", "candidate_match"],
    )
