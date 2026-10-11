"""Stream a bounded AOI subset of a real CRISM MTRDR cube from the PDS archive.

GDAL ``/vsicurl`` reads only the small ``.hdr`` plus the byte ranges for the
requested window — the full ~1 GB I/F cube is NEVER downloaded. The subset is
written as a local ENVI cube carrying the real wavelengths + Mars CRS, so the
engine reads it exactly like the bundled sample. Returns ``None`` on any failure
(the caller must not substitute synthetic data for a real request).

Note: MTRDR cubes are band-sequential, so each band is a separate range read —
reading all bands for a window is latency-bound (seconds→minutes). Keep the AOI
small (``archive_subset_px``). This is on-demand single-run streaming, not instant.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.logging import get_logger

_log = get_logger("marsgis.cubefetch")

_GDAL_ENV = {
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".img,.hdr,.lbl,.tab,.IMG,.HDR",
    "VSI_CACHE": "TRUE",
    "GDAL_HTTP_MAX_RETRY": "2",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "PROJ_IGNORE_CELESTIAL_BODY": "YES",
}


def _to_ode_lon(lon: float) -> float:
    return lon + 360.0 if lon < 0 else lon


def _resolve_mtrdr_urls(settings: Settings, observation_id: str, bbox) -> dict[str, str] | None:
    """Find the IF cube .img/.hdr (+ wavelength .tab) URLs for the observation via ODE."""
    w, s, e, n = bbox
    params = {
        "query": "product",
        "target": "mars",
        "ihid": "MRO",
        "iid": "CRISM",
        "pt": "MTRDR",
        "results": "f",
        "output": "JSON",
        "westernlon": _to_ode_lon(w),
        "easternlon": _to_ode_lon(e),
        "minlat": s,
        "maxlat": n,
        "pagelength": 20,
    }
    try:
        r = httpx.get(settings.ode_base_url, params=params, timeout=settings.ode_timeout_s)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.ode_failed", error=str(exc))
        return None

    container = data.get("ODEResults") or data
    products = container.get("Products") or {}
    plist = products.get("Product") if isinstance(products, dict) else products
    if isinstance(plist, dict):
        plist = [plist]
    base = observation_id.lower()
    for p in plist or []:
        if not isinstance(p, dict):
            continue
        pf = p.get("Product_files") or {}
        files = pf.get("Product_file") if isinstance(pf, dict) else pf
        if isinstance(files, dict):
            files = [files]
        found: dict[str, str] = {}
        for f in files or []:
            url = str(f.get("URL") or "")
            name = url.rsplit("/", 1)[-1].lower()
            if not name.startswith(base):
                continue
            if re.search(r"_if\d+.?_mtr3\.img$", name):
                found["img"] = url
            elif re.search(r"_if\d+.?_mtr3\.hdr$", name):
                found["hdr"] = url
            elif re.search(r"_wv\d+.?_mtr3\.tab$", name):
                found["wv"] = url
        if "img" in found and "hdr" in found:
            return found
    return None


def _parse_hdr(text: str) -> dict[str, Any]:
    def _num(pat: str) -> str | None:
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _block(key: str) -> list[str]:
        m = re.search(rf"{key}\s*=\s*\{{([^}}]*)\}}", text, re.IGNORECASE | re.DOTALL)
        return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []

    return {
        "bands": int(_num(r"\bbands\s*=\s*(\d+)") or 0),
        "wavelengths": _block("wavelength"),
        "bbl": _block("bbl"),
        "wavelength_units": _num(r"wavelength units\s*=\s*(\w+)") or "Nanometers",
        "data_ignore": _num(r"data ignore value\s*=\s*([-\d.eE+]+)"),
    }


def _write_envi(base_path: Path, arr, meta: dict[str, Any], transform, crs_wkt: str | None) -> None:
    import numpy as np

    bands, lines, samples = arr.shape
    img = base_path.with_suffix(".img")
    hdr = base_path.with_suffix(".hdr")
    with open(img, "wb") as fh:
        for b in range(bands):
            fh.write(np.ascontiguousarray(arr[b], dtype="<f4").tobytes())

    xsize = abs(transform.a)
    ysize = abs(transform.e)
    origin_x = transform.c
    origin_y = transform.f
    out = [
        "ENVI",
        "description = { MarsGIS AOI subset streamed from a real CRISM MTRDR cube (PDS). }",
        f"samples = {samples}",
        f"lines   = {lines}",
        f"bands   = {bands}",
        "header offset = 0",
        "file type = ENVI Standard",
        "data type = 4",
        "interleave = bsq",
        "byte order = 0",
    ]
    if meta.get("data_ignore"):
        out.append(f"data ignore value = {meta['data_ignore']}")
    out.append(f"wavelength units = {meta.get('wavelength_units', 'Nanometers')}")
    if crs_wkt:
        out.append(
            "map info = {Equirectangular, 1.0, 1.0, "
            f"{origin_x:.6f}, {origin_y:.6f}, {xsize:.6f}, {ysize:.6f}, Mars, units=Meters}}"
        )
        out.append(f"coordinate system string = {{{crs_wkt}}}")
    wls = meta.get("wavelengths") or []
    if len(wls) == bands:
        out.append("wavelength = {\n " + ",\n ".join(wls) + "}")
    bbl = meta.get("bbl") or []
    if len(bbl) == bands:
        out.append("bbl = {\n " + ",\n ".join(bbl) + "}")
    hdr.write_text("\n".join(out) + "\n")


def fetch_subset_cube(settings: Settings, observation_id: str, bbox, out_dir: Path) -> Path | None:
    """Stream a bounded AOI subset of the observation's MTRDR cube to a local ENVI
    file and return its ``.img`` path (or ``None`` on failure)."""
    import os

    import rasterio
    from rasterio.windows import Window

    urls = _resolve_mtrdr_urls(settings, observation_id, bbox)
    if not urls:
        _log.warning("cubefetch.no_urls", obs=observation_id)
        return None
    try:
        hdr_text = httpx.get(urls["hdr"], timeout=settings.archive_http_timeout_s).text
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.hdr_failed", error=str(exc))
        return None
    meta = _parse_hdr(hdr_text)

    px = settings.archive_subset_px
    saved = {k: os.environ.get(k) for k in (*_GDAL_ENV, "GDAL_HTTP_TIMEOUT")}
    os.environ.update(_GDAL_ENV)
    os.environ["GDAL_HTTP_TIMEOUT"] = str(settings.archive_http_timeout_s)
    try:
        with rasterio.open("/vsicurl/" + urls["img"]) as ds:
            width, height = ds.width, ds.height
            wp = min(px, width, height)
            c0 = max(0, width // 2 - wp // 2)
            r0 = max(0, height // 2 - wp // 2)
            win = Window(c0, r0, min(wp, width - c0), min(wp, height - r0))
            arr = ds.read(window=win).astype("float32")
            transform = ds.window_transform(win)
            crs_wkt = ds.crs.to_wkt() if ds.crs else None
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.read_failed", error=str(exc))
        return None
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    if arr.ndim != 3 or arr.shape[0] < 2:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    base_path = out_dir / f"{observation_id}_subset"
    try:
        _write_envi(base_path, arr, meta, transform, crs_wkt)
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.write_failed", error=str(exc))
        return None
    _log.info("cubefetch.subset_ready", obs=observation_id, shape=str(arr.shape))
    return base_path.with_suffix(".img")
