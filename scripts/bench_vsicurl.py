#!/usr/bin/env python3
"""A3 evidence: instrumented remote (/vsicurl) vs. local CRISM read benchmark.

Proves — with recorded numbers rather than a promise — what it costs to process
a bounded AOI of a real ~1 GB CRISM MTRDR cube straight from the PDS archive via
GDAL ``/vsicurl`` range reads. Records: URL-resolution + header time, the window
read time, the bytes transferred and HTTP range-request count (parsed from GDAL
VSICURL debug), and the AOI's shape/stats. With ``--with-local`` it also streams
the full cube once to a temp cache and asserts the AOI read remotely is
numerically identical to the AOI read locally.

No download-reduction figure is asserted anywhere; the transferred-bytes number
this script records is the only basis for any such claim.

Run (network + minutes):
    python scripts/bench_vsicurl.py
    python scripts/bench_vsicurl.py --with-local   # also verifies remote == local

Writes docs/evidence/A3_vsicurl_benchmark.json (+ .md).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
EVIDENCE = ROOT / "docs" / "evidence"

# Default target: a real, seed-catalogued Nili Fossae CRISM MTRDR observation.
DEFAULT_OBS = "frt00003e12"
DEFAULT_BBOX = (76.9404, 22.1347, 77.2127, 22.3863)  # (w, s, e, n)

_RANGE_RE = re.compile(r"Downloading (\d+)-(\d+)")


class _CurlStats(logging.Handler):
    """Capture GDAL VSICURL debug lines and tally range-request bytes/count."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.n_requests = 0
        self.bytes = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        m = _RANGE_RE.search(msg)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            self.n_requests += 1
            self.bytes += max(0, b - a + 1)


def _centered_window(width: int, height: int, px: int):
    from rasterio.windows import Window

    wp = min(px, width, height)
    c0 = max(0, width // 2 - wp // 2)
    r0 = max(0, height // 2 - wp // 2)
    return Window(c0, r0, min(wp, width - c0), min(wp, height - r0))


def _read_remote(img_url: str, px: int, gdal_env: dict[str, str]) -> dict[str, Any]:
    """Open the cube over /vsicurl, read a centered AOI, tally transfer stats."""
    import numpy as np
    import rasterio

    stats = _CurlStats()
    rio_log = logging.getLogger("rasterio")
    prev_level = rio_log.level
    rio_log.setLevel(logging.DEBUG)
    rio_log.addHandler(stats)

    saved = {k: os.environ.get(k) for k in gdal_env}
    os.environ.update(gdal_env)
    t0 = time.perf_counter()
    try:
        with (
            rasterio.Env(CPL_DEBUG=True, CPL_CURL_VERBOSE=True),
            rasterio.open("/vsicurl/" + img_url) as ds,
        ):
            win = _centered_window(ds.width, ds.height, px)
            arr = ds.read(window=win).astype("float32")
            full_shape = (ds.count, ds.height, ds.width)
    finally:
        dt = time.perf_counter() - t0
        rio_log.removeHandler(stats)
        rio_log.setLevel(prev_level)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    finite = np.isfinite(arr)
    return {
        "window_read_time_s": round(dt, 3),
        "full_cube_shape_bands_lines_samples": list(full_shape),
        "aoi_shape_bands_lines_samples": list(arr.shape),
        "n_http_range_requests": stats.n_requests or None,
        "bytes_transferred": stats.bytes or None,
        "bytes_transferred_mib": round(stats.bytes / 1048576, 3) if stats.bytes else None,
        "aoi_finite_fraction": round(float(finite.mean()), 4),
        "_arr": arr,  # popped before serialisation; used for --with-local compare
    }


def _read_local(img_url: str, px: int, cache_dir: Path) -> dict[str, Any]:
    """Stream the FULL cube to a temp cache, read the same AOI locally."""
    import httpx
    import rasterio

    cache_dir.mkdir(parents=True, exist_ok=True)
    local_img = cache_dir / img_url.rsplit("/", 1)[-1]
    t0 = time.perf_counter()
    total = 0
    with httpx.stream("GET", img_url, timeout=120.0, follow_redirects=True) as r:
        r.raise_for_status()
        with open(local_img, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
                total += len(chunk)
    dl_dt = time.perf_counter() - t0

    with rasterio.open(str(local_img)) as ds:
        win = _centered_window(ds.width, ds.height, px)
        arr = ds.read(window=win).astype("float32")
    return {
        "full_download_time_s": round(dl_dt, 3),
        "full_download_bytes": total,
        "full_download_mib": round(total / 1048576, 3),
        "_arr": arr,
    }


def main() -> int:
    import numpy as np
    from app.config import Settings
    from app.services.cube_fetch import _GDAL_ENV, _parse_hdr, _resolve_mtrdr_urls

    ap = argparse.ArgumentParser(description="A3 /vsicurl remote-vs-local benchmark")
    ap.add_argument("--observation", default=DEFAULT_OBS)
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"),
                    default=list(DEFAULT_BBOX))
    ap.add_argument("--px", type=int, default=None, help="AOI window size (default: settings)")
    ap.add_argument("--with-local", action="store_true",
                    help="also download the FULL cube once and verify remote == local")
    args = ap.parse_args()

    settings = Settings()
    px = args.px or settings.archive_subset_px
    obs = args.observation
    bbox = tuple(args.bbox)

    record: dict[str, Any] = {
        "gate": "A3",
        "title": "Remote /vsicurl vs. local CRISM MTRDR read",
        "observation": obs,
        "bbox_lonlat_wsen": list(bbox),
        "aoi_px": px,
        "status": "ok",
    }

    # --- Stage 1: metadata (URL resolution + .hdr) ----------------------
    import httpx

    t0 = time.perf_counter()
    urls = _resolve_mtrdr_urls(settings, obs, bbox)
    if not urls:
        record.update(status="failed", error="ODE returned no MTRDR img/hdr URLs")
        return _finish(record, 1)
    hdr_text = httpx.get(urls["hdr"], timeout=settings.archive_http_timeout_s).text
    meta = _parse_hdr(hdr_text)
    record["metadata_time_s"] = round(time.perf_counter() - t0, 3)
    record["resolved_urls"] = urls
    record["declared_bands"] = meta.get("bands")

    # --- Stage 2: remote windowed read ----------------------------------
    try:
        remote = _read_remote(urls["img"], px, dict(_GDAL_ENV))
    except Exception as exc:  # noqa: BLE001
        record.update(status="failed", error=f"remote read failed: {exc}")
        return _finish(record, 1)
    remote_arr = remote.pop("_arr")
    record["remote"] = remote

    # --- Optional Stage 3: local full-download comparison ---------------
    if args.with_local:
        try:
            local = _read_local(urls["img"], px, ROOT / ".cache" / "a3")
            local_arr = local.pop("_arr")
            agree = bool(
                remote_arr.shape == local_arr.shape
                and np.array_equal(remote_arr, local_arr, equal_nan=True)
            )
            record["local"] = local
            record["remote_equals_local"] = agree
        except Exception as exc:  # noqa: BLE001
            record["local"] = {"error": str(exc)}
            record["remote_equals_local"] = None

    return _finish(record, 0)


def _finish(record: dict[str, Any], code: int) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "A3_vsicurl_benchmark.json").write_text(json.dumps(record, indent=2) + "\n")
    _write_md(record)
    r = record.get("remote", {})
    print(f"[A3] observation {record['observation']} status={record['status']}")
    if record["status"] == "ok":
        print(f"   metadata: {record.get('metadata_time_s')}s  "
              f"declared_bands={record.get('declared_bands')}")
        print(f"   AOI {r.get('aoi_shape_bands_lines_samples')} read in "
              f"{r.get('window_read_time_s')}s")
        print(f"   transfer: {r.get('bytes_transferred_mib')} MiB over "
              f"{r.get('n_http_range_requests')} range requests")
        if "remote_equals_local" in record:
            print(f"   remote == local: {record['remote_equals_local']}")
    else:
        print(f"   ERROR: {record.get('error')}")
    print(f"[A3] evidence -> {EVIDENCE / 'A3_vsicurl_benchmark.json'}")
    return code


def _write_md(record: dict[str, Any]) -> None:
    r = record.get("remote", {})
    lines = [
        "# A3 — Remote `/vsicurl` vs. local CRISM read",
        "",
        f"- Observation: `{record['observation']}`  bbox (W,S,E,N): {record['bbox_lonlat_wsen']}",
        f"- AOI window: {record['aoi_px']} px   status: **{record['status']}**",
    ]
    if record["status"] == "ok":
        lines += [
            f"- Metadata (resolve + header): **{record.get('metadata_time_s')} s**",
            (
                f"- Full cube: {r.get('full_cube_shape_bands_lines_samples')} "
                f"(bands, lines, samples); declared bands {record.get('declared_bands')}"
            ),
            (
                f"- AOI read: {r.get('aoi_shape_bands_lines_samples')} in "
                f"**{r.get('window_read_time_s')} s**"
            ),
            (
                f"- Transferred: **{r.get('bytes_transferred_mib')} MiB** over "
                f"**{r.get('n_http_range_requests')}** HTTP range requests "
                "(parsed from GDAL VSICURL debug; `null` = not surfaced by this GDAL build)"
            ),
        ]
        if "remote_equals_local" in record:
            loc = record.get("local", {})
            lines.append(
                f"- Remote == local: **{record['remote_equals_local']}** "
                f"(full download {loc.get('full_download_mib')} MiB in "
                f"{loc.get('full_download_time_s')} s)"
            )
        lines += [
            "",
            (
                "No download-reduction percentage is claimed except directly from the "
                "transferred-bytes figure above versus the full-cube size."
            ),
        ]
    else:
        lines.append(f"- Error: {record.get('error')}")
    (EVIDENCE / "A3_vsicurl_benchmark.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
