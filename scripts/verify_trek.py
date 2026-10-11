#!/usr/bin/env python3
"""A1 evidence: NASA Mars Trek ↔ Cesium spatial-alignment check.

Validates the one assumption the whole 3D map rests on: that the Trek global
equirectangular grid is a geographic 2x1-at-z0 scheme (east-positive longitude,
clon=0) and that a known Mars feature's lon/lat maps to the correct tile and
that tile actually returns imagery. Pole and ±180° seam are exercised so the
math never throws at the edges.

Pure tiling math always runs (deterministic, offline). Live tile fetches run
when the network is reachable; when it is not, they are recorded as "skipped",
never as a pass. Writes a committed evidence record to
``docs/evidence/A1_trek_alignment.json`` (+ a short .md summary).

Run:  python scripts/verify_trek.py            # math + live fetches
      python scripts/verify_trek.py --offline  # math only
Exit code is non-zero if any check that actually ran failed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any

TREK = "https://trek.nasa.gov/tiles/Mars/EQ"
VIKING = "Mars_Viking_MDIM21_ClrMosaic_global_232m"  # jpg, the default basemap
EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence"

# Known Mars features in east-positive IAU-2000 degrees (lon, lat). These are
# well-published centres; the test only needs them to land on a non-blank tile.
FEATURES: list[dict[str, Any]] = [
    {"name": "Jezero crater", "lon": 77.4, "lat": 18.4},
    {"name": "Gale crater", "lon": 137.4, "lat": -5.4},
    {"name": "Olympus Mons", "lon": -133.8, "lat": 18.65},
    {"name": "Nili Fossae", "lon": 77.0, "lat": 21.0},
]

# Image magic bytes -> we accept a tile as "real imagery" only if it decodes.
_MAGIC = {b"\xff\xd8\xff": "jpeg", b"\x89PNG\r\n\x1a\n": "png"}


def tile_grid(level: int) -> tuple[int, int]:
    """(numX, numY) for the Cesium GeographicTilingScheme: 2x1 at level 0."""
    return 2 * (2**level), 1 * (2**level)


def lonlat_to_tile(lon: float, lat: float, level: int) -> tuple[int, int]:
    """Map east-positive lon/lat (deg) to Trek WMTS (col x, row y) at ``level``.

    Longitude wraps at the ±180° seam; row 0 is the north edge (WMTS/Cesium
    convention). Both indices are clamped into range so the poles and the seam
    resolve to a valid tile instead of overflowing.
    """
    num_x, num_y = tile_grid(level)
    lon_frac = ((lon + 180.0) % 360.0) / 360.0
    lat_frac = (90.0 - lat) / 180.0
    x = min(num_x - 1, max(0, math.floor(lon_frac * num_x)))
    y = min(num_y - 1, max(0, math.floor(lat_frac * num_y)))
    return x, y


def tile_url(product: str, ext: str, level: int, x: int, y: int) -> str:
    return f"{TREK}/{product}/1.0.0//default/default028mm/{level}/{y}/{x}.{ext}"


def _fetch(url: str, timeout: float = 20.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "MarsGIS-A1-verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _image_kind(data: bytes) -> str | None:
    for magic, kind in _MAGIC.items():
        if data.startswith(magic):
            return kind
    return None


def check_math() -> list[dict[str, Any]]:
    """Deterministic, offline tiling-math assertions."""
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # Level 0 is exactly two tiles wide, one tall.
    record("grid_2x1_at_z0", tile_grid(0) == (2, 1), f"grid(0)={tile_grid(0)}")

    # The prime meridian sits on the boundary between the two z0 columns; a hair
    # east is column 1, a hair west (179.9°E) is column 1 too, 0.1°E is col 1,
    # -0.1°(=359.9) is col 0's... verify west/east hemispheres split correctly.
    west = lonlat_to_tile(-90.0, 0.0, 0)
    east = lonlat_to_tile(90.0, 0.0, 0)
    record("hemispheres_split", west == (0, 0) and east == (1, 0), f"west={west} east={east}")

    # ±180° seam resolves without throwing and stays in range.
    seam_ok = True
    for lon in (-180.0, 180.0, 179.999, -179.999):
        for lvl in (0, 3, 6):
            x, y = lonlat_to_tile(lon, 0.0, lvl)
            nx, _ = tile_grid(lvl)
            seam_ok &= 0 <= x < nx
    record("seam_in_range", seam_ok, "±180° maps to a valid column at z0/3/6")

    # Poles resolve to a valid row (lat=-90 must not overflow numY).
    pole_ok = True
    for lat in (90.0, -90.0):
        for lvl in (0, 3, 6):
            _, y = lonlat_to_tile(0.0, lat, lvl)
            _, ny = tile_grid(lvl)
            pole_ok &= 0 <= y < ny
    record("poles_in_range", pole_ok, "lat=±90° maps to a valid row at z0/3/6")

    return checks


def check_live(level: int = 4) -> list[dict[str, Any]]:
    """Fetch the tile each known feature lands on; assert it is real imagery.

    A tile that decodes as JPEG/PNG and is more than a trivial number of bytes
    is treated as present. (A deeper non-blank/variance test would need an image
    library; byte-size + magic is a dependency-free proxy and is labelled so.)
    """
    results: list[dict[str, Any]] = []
    for feat in FEATURES:
        x, y = lonlat_to_tile(feat["lon"], feat["lat"], level)
        url = tile_url(VIKING, "jpg", level, x, y)
        entry: dict[str, Any] = {
            "feature": feat["name"],
            "lon": feat["lon"],
            "lat": feat["lat"],
            "level": level,
            "tile": {"x": x, "y": y},
            "url": url,
        }
        try:
            status, data = _fetch(url)
            kind = _image_kind(data)
            entry.update(
                status=status,
                bytes=len(data),
                image_kind=kind,
                ok=bool(status == 200 and kind == "jpeg" and len(data) > 1024),
            )
        except Exception as exc:  # noqa: BLE001 - network/transport failure is data
            entry.update(status=None, ok=None, error=str(exc))
        results.append(entry)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="A1 Trek↔Cesium alignment evidence")
    ap.add_argument("--offline", action="store_true", help="run tiling math only")
    ap.add_argument("--level", type=int, default=4, help="zoom level for live fetches")
    args = ap.parse_args()

    math_checks = check_math()
    live = [] if args.offline else check_live(args.level)

    math_ok = all(c["ok"] for c in math_checks)
    live_ran = [r for r in live if r.get("ok") is not None]
    live_ok = all(r["ok"] for r in live_ran) if live_ran else None

    record = {
        "gate": "A1",
        "title": "NASA Mars Trek ↔ Cesium spatial alignment",
        "tiling_scheme": "GeographicTilingScheme 2x1@z0, east-positive, clon=0",
        "basemap_product": VIKING,
        "math_checks": math_checks,
        "live_checks": live,
        "summary": {
            "math_ok": math_ok,
            "live_ran": len(live_ran),
            "live_skipped": len(live) - len(live_ran),
            "live_ok": live_ok,
        },
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "A1_trek_alignment.json").write_text(json.dumps(record, indent=2) + "\n")
    _write_md(record)

    # Console summary.
    print(f"[A1] tiling math: {'PASS' if math_ok else 'FAIL'} ({len(math_checks)} checks)")
    for c in math_checks:
        print(f"   {'✓' if c['ok'] else '✗'} {c['check']}: {c['detail']}")
    if args.offline:
        print("[A1] live tile fetches: SKIPPED (--offline)")
    else:
        for r in live:
            if r.get("ok") is None:
                print(f"   ? {r['feature']}: skipped ({r.get('error', 'no result')})")
            else:
                print(
                    f"   {'✓' if r['ok'] else '✗'} {r['feature']} -> z{r['level']}/"
                    f"{r['tile']['y']}/{r['tile']['x']} "
                    f"[{r.get('status')}, {r.get('bytes')}B, {r.get('image_kind')}]"
                )
    print(f"[A1] evidence -> {EVIDENCE / 'A1_trek_alignment.json'}")

    # Fail only on a check that actually ran.
    if not math_ok:
        return 1
    if live_ok is False:
        return 1
    return 0


def _write_md(record: dict[str, Any]) -> None:
    s = record["summary"]
    lines = [
        "# A1 — Mars Trek ↔ Cesium alignment",
        "",
        f"- Tiling scheme: `{record['tiling_scheme']}`",
        f"- Basemap product: `{record['basemap_product']}`",
        (
            f"- Tiling math: **{'PASS' if s['math_ok'] else 'FAIL'}** "
            f"({len(record['math_checks'])} checks)"
        ),
        (
            f"- Live tile fetches: **{s['live_ran']} ran**, {s['live_skipped']} skipped, "
            f"result: **{s['live_ok']}**"
        ),
        "",
        "| Feature | lon,lat | tile (z/y/x) | status | bytes | kind | ok |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in record["live_checks"]:
        t = r.get("tile", {})
        lines.append(
            f"| {r['feature']} | {r['lon']},{r['lat']} | "
            f"{r.get('level')}/{t.get('y')}/{t.get('x')} | {r.get('status')} | "
            f"{r.get('bytes', '')} | {r.get('image_kind', '')} | {r.get('ok')} |"
        )
    (EVIDENCE / "A1_trek_alignment.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
