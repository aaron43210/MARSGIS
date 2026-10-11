"""On-the-fly COG tiling / preview / bounds over the custom Mars geographic TMS.

Color is baked server-side: the SAM angle is rendered with ``magma_r`` over
``[0, threshold]`` and angles above the threshold (and nodata) are transparent.
rio-tiler reprojects the engine COG from its native Mars CRS onto the Mars
geographic tile grid, so overlays co-register with the Trek basemaps.
"""

from __future__ import annotations

from pathlib import Path

from app.core.colormaps import get_colormap
from app.core.constants import MARS2000_GEOGRAPHIC_WKT, SAM_ANGLE_COLORMAP
from app.core.tms import get_tms
from app.logging import get_logger

_log = get_logger("marsgis.raster")


def geographic_bounds(cog_path: Path) -> tuple[float, float, float, float]:
    """Return the raster extent as Mars degrees [west, south, east, north]."""
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(cog_path) as ds:
        src_crs = ds.crs
        left, bottom, right, top = ds.bounds
        if src_crs is None:
            return (float(left), float(bottom), float(right), float(top))
        try:
            w, s, e, n = transform_bounds(
                src_crs, MARS2000_GEOGRAPHIC_WKT, left, bottom, right, top, densify_pts=21
            )
            return (float(w), float(s), float(e), float(n))
        except Exception as exc:  # pragma: no cover - projection edge cases
            _log.warning("raster.bounds_transform_failed", error=str(exc))
            return (float(left), float(bottom), float(right), float(top))


def _render(img, value_range: tuple[float, float], colormap_name: str) -> bytes:
    """Mask angles above the value-range max, rescale, apply colormap -> PNG."""
    import numpy as np
    from rio_tiler.models import ImageData

    lo, hi = value_range
    arr = img.array  # numpy MaskedArray (bands, h, w)
    masked = np.ma.masked_invalid(arr)
    masked = np.ma.masked_greater(masked, hi)
    out = ImageData(masked, crs=getattr(img, "crs", None), bounds=getattr(img, "bounds", None))
    out.rescale(in_range=((lo, hi),), out_range=((0, 255),))
    colormap = get_colormap(colormap_name)
    return out.render(img_format="PNG", colormap=colormap, add_mask=True)


def tile(
    cog_path: Path,
    z: int,
    x: int,
    y: int,
    *,
    value_range: tuple[float, float],
    colormap_name: str = SAM_ANGLE_COLORMAP,
    tile_size: int = 256,
) -> bytes | None:
    """Render one PNG tile, or None when the tile does not intersect the raster."""
    from rio_tiler.errors import TileOutsideBounds
    from rio_tiler.io import Reader

    tms = get_tms()
    with Reader(str(cog_path), tms=tms) as reader:
        if not reader.tile_exists(x, y, z):
            return None
        try:
            img = reader.tile(x, y, z, tilesize=tile_size)
        except TileOutsideBounds:
            return None
    import numpy as np

    if img.array.mask is not np.ma.nomask and bool(img.array.mask.all()):
        return None
    return _render(img, value_range, colormap_name)


def preview(
    cog_path: Path,
    *,
    value_range: tuple[float, float],
    colormap_name: str = SAM_ANGLE_COLORMAP,
    max_size: int = 1024,
) -> bytes:
    """Render a downsampled full-extent PNG (SingleTile fallback for tiny AOIs)."""
    from rio_tiler.io import Reader

    max_size = max(16, min(2048, max_size))
    tms = get_tms()
    with Reader(str(cog_path), tms=tms) as reader:
        img = reader.preview(max_size=max_size)
    return _render(img, value_range, colormap_name)


def compute_summary_stats(
    angle_path: Path,
    mask_path: Path | None,
    *,
    threshold_rad: float,
) -> dict:
    """Compute pixel/candidate statistics directly from the angle (+mask) rasters."""
    import numpy as np
    import rasterio

    with rasterio.open(angle_path) as ds:
        arr = ds.read(1, masked=True).astype("float64")
        nodata = ds.nodata

    data = np.ma.masked_invalid(arr)
    if nodata is not None:
        data = np.ma.masked_equal(data, nodata)

    pixel_count = int(data.size)
    valid = data.compressed()
    valid_count = int(valid.size)

    detected = valid[valid <= threshold_rad] if valid_count else valid
    detected_count = int(detected.size)
    detected_fraction = (detected_count / valid_count) if valid_count else 0.0

    def _f(fn, default=None):
        return float(fn(valid)) if valid_count else default

    stats = {
        "pixel_count": pixel_count,
        "valid_pixel_count": valid_count,
        "detected_pixel_count": detected_count,
        "detected_fraction": round(detected_fraction, 6),
        "min": _f(np.min),
        "max": _f(np.max),
        "mean": _f(np.mean),
        "median": _f(np.median),
        "std": _f(np.std),
    }
    if valid_count:
        counts, edges = np.histogram(valid, bins=16)
        stats["histogram"] = {
            "bin_edges": [float(e) for e in edges.tolist()],
            "counts": [int(c) for c in counts.tolist()],
        }
    return stats
