"""Point elevation sampling from the global MOLA DEM.

The DEM is a remote Cloud-Optimized GeoTIFF (public-domain NASA/USGS MOLA 463 m
global topography). GDAL ``/vsicurl`` reads only the header plus the single strip
covering the requested pixel over HTTP range requests — the multi-GB file is
NEVER downloaded in full. Any failure (offline, timeout, nodata, out of range)
returns ``None`` so the UI read-out degrades gracefully instead of erroring.

Coordinates in are Mars IAU 2000 geographic degrees (east-positive lon
[-180,180], planetocentric lat [-90,90]); the DEM is a Mars equirectangular
projection on the same 3,396,190 m sphere, so the transform stays on-body.
"""

from __future__ import annotations

import os
import threading

from app.config import get_settings
from app.logging import get_logger

_log = get_logger("marsgis.elevation")

# GDAL /vsicurl tuning: short timeouts, don't scan the bucket, cache fetched blocks.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "1")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "1")

_lock = threading.Lock()
_dataset = None  # cached rasterio DatasetReader (opened once, reused)
_to_dem = None  # pyproj Transformer: lon/lat deg -> DEM CRS
_NODATA_FLOOR = -32768.0


def _open() -> tuple[object, object]:
    """Lazily open the remote DEM and build the lon/lat -> DEM-CRS transformer."""
    global _dataset, _to_dem
    if _dataset is None:
        import rasterio
        from pyproj import Transformer

        settings = get_settings()
        os.environ["GDAL_HTTP_TIMEOUT"] = str(settings.elevation_http_timeout_s)
        url = f"/vsicurl/{settings.mola_dem_url}"
        ds = rasterio.open(url)
        _to_dem = Transformer.from_crs(
            "+proj=longlat +R=3396190 +no_defs", ds.crs.to_wkt(), always_xy=True
        )
        _dataset = ds
        _log.info("elevation.dem_opened", size=f"{ds.width}x{ds.height}")
    return _dataset, _to_dem


def _reset() -> None:
    global _dataset, _to_dem
    try:
        if _dataset is not None:
            _dataset.close()
    except Exception:  # noqa: BLE001
        pass
    _dataset = None
    _to_dem = None


def sample_elevation(lon: float, lat: float) -> float | None:
    """Return the MOLA elevation (metres) at ``lon``/``lat``, or ``None``.

    Blocking (network + raster read); call from a worker thread.
    """
    settings = get_settings()
    if not settings.elevation_enabled:
        return None
    try:
        lon = float(lon)
        lat = float(lat)
    except (TypeError, ValueError):
        return None
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        return None

    try:
        with _lock:
            ds, tr = _open()
            x, y = tr.transform(lon, lat)
            row, col = ds.index(x, y)
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                return None
            value = ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
            nodata = ds.nodata
    except Exception as exc:  # noqa: BLE001 - network/raster errors must not 500
        _log.warning("elevation.sample_failed", error=str(exc))
        with _lock:
            _reset()  # drop the handle so a transient error can recover next call
        return None

    v = float(value)
    if (nodata is not None and v == float(nodata)) or v <= _NODATA_FLOOR:
        return None
    return round(v, 1)
