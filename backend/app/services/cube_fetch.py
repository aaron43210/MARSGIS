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
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.core.tls import ca_bundle_path, ssl_context
from app.logging import get_logger

_log = get_logger("marsgis.cubefetch")

_GDAL_ENV = {
    # The ENVI driver must see the sibling .hdr; a process-wide EMPTY_DIR (set for
    # the elevation COG) would hide it and the cube would fail to open.
    "GDAL_DISABLE_READDIR_ON_OPEN": "FALSE",
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
        r = httpx.get(
            settings.ode_base_url,
            params=params,
            timeout=settings.ode_timeout_s,
            verify=ssl_context(),
        )
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
        "samples": int(_num(r"\bsamples\s*=\s*(\d+)") or 0),
        "lines": int(_num(r"\blines\s*=\s*(\d+)") or 0),
        "header_offset": int(_num(r"header offset\s*=\s*(\d+)") or 0),
        "data_type": int(_num(r"data type\s*=\s*(\d+)") or 0),
        "interleave": (_num(r"interleave\s*=\s*(\w+)") or "").lower(),
        "byte_order": int(_num(r"byte order\s*=\s*(\d+)") or 0),
        "bands": int(_num(r"\bbands\s*=\s*(\d+)") or 0),
        "wavelengths": _block("wavelength"),
        "bbl": _block("bbl"),
        "wavelength_units": _num(r"wavelength units\s*=\s*(\w+)") or "Nanometers",
        "data_ignore": _num(r"data ignore value\s*=\s*([-\d.eE+]+)"),
    }


# ENVI "data type" codes -> numpy dtype names.
_ENVI_DTYPES = {1: "u1", 2: "i2", 3: "i4", 4: "f4", 5: "f8", 12: "u2", 13: "u4"}


def _read_bsq_window(
    settings: Settings,
    img_url: str,
    meta: dict[str, Any],
    c0: int,
    r0: int,
    w: int,
    h: int,
    *,
    out=None,
    progress=None,
):
    """Read a window of every band with ONE HTTP range request per band, in parallel.

    In a band-sequential (BSQ) cube the rows of one band are contiguous, so the window's
    rows for a band are a single byte range (full width, then cropped). GDAL instead
    fetches row blocks one by one, which over a high-latency link took ~20-50 s per
    band (hours per cube). Returns ``None`` if the layout is not plain BSQ.
    """
    import numpy as np

    code = _ENVI_DTYPES.get(meta.get("data_type", 0))
    if meta.get("interleave") != "bsq" or code is None or not meta.get("samples"):
        return None
    dtype = np.dtype(("<" if meta.get("byte_order", 0) == 0 else ">") + code)
    width, lines, bands = meta["samples"], meta["lines"], meta["bands"]
    row_bytes = width * dtype.itemsize
    band_bytes = row_bytes * lines
    n_bytes = row_bytes * h
    if out is None:
        out = np.empty((bands, h, w), dtype="float32")

    from concurrent.futures import ThreadPoolExecutor

    def fetch(client, b: int) -> None:
        start = meta.get("header_offset", 0) + b * band_bytes + r0 * row_bytes
        rng = f"bytes={start}-{start + n_bytes - 1}"
        for attempt in range(3):
            try:
                resp = client.get(img_url, headers={"Range": rng})
                resp.raise_for_status()
                buf = resp.content
                if resp.status_code != 206 or len(buf) != n_bytes:
                    raise ValueError(f"band {b}: got {len(buf)} bytes, status {resp.status_code}")
                rows = np.frombuffer(buf, dtype=dtype).reshape(h, width)
                out[b] = rows[:, c0 : c0 + w].astype("float32")
                return
            except Exception:  # noqa: BLE001 - retried, then surfaced
                if attempt == 2:
                    raise

    limits = httpx.Limits(max_connections=settings.archive_parallel_requests)
    with (
        httpx.Client(
            timeout=settings.archive_http_timeout_s, verify=ssl_context(), limits=limits
        ) as client,
        ThreadPoolExecutor(settings.archive_parallel_requests) as pool,
    ):
        from concurrent.futures import as_completed

        futures = [pool.submit(fetch, client, b) for b in range(bands)]
        # Report progress from THIS (the caller's) thread: the job's progress bridge
        # only works from the worker thread anyio started, not from pool threads.
        for n, fut in enumerate(as_completed(futures), start=1):
            fut.result()
            if progress is not None:
                progress(n, bands)
    return out


def _write_envi(base_path: Path, arr, meta: dict[str, Any], transform, crs_wkt: str | None) -> None:
    import numpy as np

    with open(base_path.with_suffix(".img"), "wb") as fh:
        for b in range(arr.shape[0]):
            fh.write(np.ascontiguousarray(arr[b], dtype="<f4").tobytes())
    _write_envi_header(base_path, arr.shape, meta, transform, crs_wkt)


def _write_envi_header(
    base_path: Path,
    shape: tuple[int, int, int],
    meta: dict[str, Any],
    transform,
    crs_wkt: str | None,
) -> None:
    bands, lines, samples = shape
    hdr = base_path.with_suffix(".hdr")

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


def _strip_start(ds, rows: int, center: tuple[float, float] | None) -> int:
    """First row of a ``rows``-tall, FULL-WIDTH strip centred on ``center`` (Mars
    lon/lat) or on the image centre, clamped inside the image.

    Full width costs nothing extra: in a band-sequential cube every range request
    already returns whole rows, so a strip covers the observation from edge to edge
    for the same download as a small square.
    """
    height = ds.height
    if center is not None and ds.crs is not None:
        from rasterio.warp import transform

        from app.core.constants import MARS2000_GEOGRAPHIC_WKT

        xs, ys = transform(MARS2000_GEOGRAPHIC_WKT, ds.crs, [center[0]], [center[1]])
        row, _ = ds.index(xs[0], ys[0])
    else:
        row = height // 2
    return min(max(0, row - rows // 2), max(0, height - rows))


def fetch_subset_cube(
    settings: Settings,
    observation_id: str,
    bbox,
    out_dir: Path,
    *,
    center: tuple[float, float] | None = None,
    stem: str | None = None,
    rows: int | None = None,
    progress=None,
) -> Path | None:
    """Stream a full-width strip of ``rows`` lines (``None`` = the whole image) of the
    observation's MTRDR cube to a local ENVI file; return its ``.img`` path (or
    ``None`` on failure). The strip is centred on ``center`` (Mars lon/lat) when
    given, else on the image centre. ``progress(done, total)`` reports bands read."""
    import os

    import rasterio
    from rasterio.windows import Window

    urls = _resolve_mtrdr_urls(settings, observation_id, bbox)
    if not urls:
        _log.warning("cubefetch.no_urls", obs=observation_id)
        return None
    try:
        hdr_text = httpx.get(
            urls["hdr"], timeout=settings.archive_http_timeout_s, verify=ssl_context()
        ).text
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.hdr_failed", error=str(exc))
        return None
    meta = _parse_hdr(hdr_text)

    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    base_path = out_dir / (stem or f"{observation_id}_subset")
    # Unique per download: two jobs streaming the same new area must not share a file.
    tmp_base = base_path.with_name(f"{base_path.name}_partial_{uuid.uuid4().hex}")
    # Thread-local GDAL config options (rasterio.Env) override process-wide env vars,
    # so other features' GDAL settings can neither break nor be broken by this read.
    gdal_opts = {
        **_GDAL_ENV,
        "CURL_CA_BUNDLE": ca_bundle_path(),
        "GDAL_HTTP_TIMEOUT": str(settings.archive_http_timeout_s),
    }
    saved = {k: os.environ.get(k) for k in ("PROJ_IGNORE_CELESTIAL_BODY",)}
    os.environ["PROJ_IGNORE_CELESTIAL_BODY"] = "YES"
    try:
        with rasterio.Env(**gdal_opts), rasterio.open("/vsicurl/" + urls["img"]) as ds:
            width, height = ds.width, ds.height
            h = height if rows is None else max(1, min(int(rows), height))
            r0 = _strip_start(ds, h, center)
            win = Window(0, r0, width, h)
            transform = ds.window_transform(win)
            crs_wkt = ds.crs.to_wkt() if ds.crs else None
            # Stream straight to disk: a whole image (~1.4 GB) never sits in memory.
            mm = None
            if meta.get("interleave") == "bsq" and meta.get("samples") == width:
                mm = np.memmap(
                    tmp_base.with_suffix(".img"),
                    dtype="<f4",
                    mode="w+",
                    shape=(meta["bands"], h, width),
                )
                arr = _read_bsq_window(
                    settings, urls["img"], meta, 0, r0, width, h, out=mm, progress=progress
                )
            else:
                arr = None
            if arr is None:  # not plain BSQ: let GDAL do it (slower)
                arr = ds.read(window=win).astype("float32")
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
    try:
        if mm is not None:
            mm.flush()
            _write_envi_header(tmp_base, arr.shape, meta, transform, crs_wkt)
        else:
            _write_envi(tmp_base, arr, meta, transform, crs_wkt)
        # Publish atomically, header last, so a half-written cube is never reused.
        tmp_base.with_suffix(".img").replace(base_path.with_suffix(".img"))
        tmp_base.with_suffix(".hdr").replace(base_path.with_suffix(".hdr"))
    except Exception as exc:  # noqa: BLE001
        _log.warning("cubefetch.write_failed", error=str(exc))
        return None
    _log.info("cubefetch.subset_ready", obs=observation_id, shape=str(arr.shape))
    return base_path.with_suffix(".img")
