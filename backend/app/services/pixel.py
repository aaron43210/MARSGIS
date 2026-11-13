"""Real per-pixel inspection of an analysis result.

Maps a clicked Mars lon/lat onto the result's angle raster, then asks the engine
for that pixel's actual spectrum next to the reference, on the exact bands SAM
used. Nothing here is synthetic: a different click returns a different pixel.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.core.constants import MARS2000_EQUIRECT_WKT, MARS2000_GEOGRAPHIC_WKT
from app.services.engine_adapter import _CLASS_TO_ALIAS


def locate(angle_path: Path, lon: float, lat: float) -> tuple[int, int, float | None] | None:
    """Return (row, col, raster_angle) for lon/lat, or None if outside the raster."""
    import rasterio
    from rasterio.warp import transform

    with rasterio.open(angle_path) as ds:
        if ds.crs is not None:
            xs, ys = transform(MARS2000_GEOGRAPHIC_WKT, ds.crs, [lon], [lat])
            x, y = xs[0], ys[0]
        else:
            x, y = lon, lat
        row, col = ds.index(x, y)
        if not (0 <= row < ds.height and 0 <= col < ds.width):
            return None
        value = float(ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
    return int(row), int(col), (value if math.isfinite(value) else None)


def inspect(
    *,
    cube_path: Path,
    angle_path: Path,
    mineral_class: str,
    lon: float,
    lat: float,
    threshold_rad: float,
    continuum_removed: bool,
    wavelength_subset_nm: list[float] | None,
    band_depth: bool = False,
) -> dict[str, Any]:
    from marsgis_engine import RunParams, inspect_pixel

    hit = locate(angle_path, lon, lat)
    if hit is None:
        return {"inside": False, "lon": lon, "lat": lat}
    row, col, raster_angle = hit
    alias = _CLASS_TO_ALIAS.get(mineral_class)
    if alias is None:
        raise ValueError(f"no engine reference for mineral class '{mineral_class}'")
    window = tuple(wavelength_subset_nm) if wavelength_subset_nm else (1000.0, 2600.0)
    params = RunParams(
        threshold_rad=threshold_rad,
        window_nm=window,
        mask_bad_bands=True,
        continuum_removal=continuum_removed,
        band_depth=band_depth,
        resample_method="linear",
        crs_fallback_wkt=MARS2000_EQUIRECT_WKT,
    )
    out = inspect_pixel(str(cube_path), alias, params, row, col)
    angle = out["angle_rad"]
    return {
        "inside": True,
        "lon": lon,
        "lat": lat,
        "row": row,
        "col": col,
        "angle_rad": angle,
        "raster_angle_rad": raster_angle,
        "threshold_rad": threshold_rad,
        "is_candidate": angle is not None and angle <= threshold_rad,
        "continuum_removed": out["continuum_removed"],
        "band_depth": out["band_depth"],
        "window_nm": out["window_nm"],
        "wavelength_nm": out["wavelength_nm"],
        "pixel": out["pixel"],
        "reference": out["reference"],
    }
