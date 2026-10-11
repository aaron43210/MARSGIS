"""Generate a tiny synthetic Mars-geographic COG for raster/job tests.

Writes a float32 SAM-angle COG (NaN nodata) with a block of low-angle "matched"
pixels over the Nili Fossae bbox, plus a companion uint8 candidate-mask COG. The
CRS is the Mars 2000 geographic WKT so tiles register on the MarsEQC TMS. This is
SYNTHETIC test data and is never presented as a real detection.
"""

from __future__ import annotations

from pathlib import Path

from app.core.constants import MARS2000_GEOGRAPHIC_WKT, NILI_FOSSAE_BBOX


def make_sample_cog(
    out_dir: Path,
    prefix: str,
    *,
    size: int = 64,
    threshold_rad: float = 0.10,
    bbox: tuple[float, float, float, float] = NILI_FOSSAE_BBOX,
) -> tuple[Path, Path]:
    import numpy as np
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w, s, e, n = bbox
    transform = from_bounds(w, s, e, n, size, size)
    crs = CRS.from_wkt(MARS2000_GEOGRAPHIC_WKT)

    # Angle raster: background ~0.5 rad (non-match), a matched block ~0.02 rad,
    # and a NaN nodata border.
    angle = np.full((size, size), 0.5, dtype="float32")
    lo = size // 4
    hi = size // 2
    angle[lo:hi, lo:hi] = 0.02
    angle[0, :] = np.nan
    angle[-1, :] = np.nan

    mask = np.where(np.isfinite(angle) & (angle <= threshold_rad), 1, 0).astype("uint8")
    mask[~np.isfinite(angle)] = 255

    angle_path = out_dir / f"{prefix}_SAM_angle.tif"
    mask_path = out_dir / f"{prefix}_SAM_candidate.tif"
    _write_cog(angle_path, angle, transform, crs, nodata=float("nan"), dtype="float32")
    _write_cog(mask_path, mask, transform, crs, nodata=255, dtype="uint8")
    return angle_path, mask_path


def _write_cog(path, array, transform, crs, *, nodata, dtype) -> None:
    import rasterio
    from rasterio.io import MemoryFile

    profile = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 16,
        "blockysize": 16,
        "compress": "deflate",
    }
    # Write a tiled GTiff in memory, then copy to a validated COG on disk.
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(array, 1)
            tmp.build_overviews([2], rasterio.enums.Resampling.nearest)
        try:
            from rasterio.shutil import copy as rio_copy

            rio_copy(mem.name, str(path), driver="COG", overview_resampling="nearest")
        except Exception:
            # Fallback: a plain tiled GTiff still reads fine for tests.
            with mem.open() as src, rasterio.open(str(path), "w", **profile) as dst:
                dst.write(src.read(1), 1)
