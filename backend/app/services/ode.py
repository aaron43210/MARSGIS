"""Live CRISM product discovery via the PDS Orbital Data Explorer (ODE) REST API.

Queries ODE for CRISM MTRDR products within a lon/lat bbox and maps each product
to an :class:`Observation` row (metadata + footprint only). No bulk download: the
actual cube is fetched on demand at analysis time. ODE reports 0..360 east
longitude; MarsGIS uses east-positive [-180, 180], so longitudes are normalised.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.db.geo import bbox_of, footprint_to_text, polygon_from_bbox
from app.db.models import Observation, utcnow
from app.logging import get_logger

_log = get_logger("marsgis.ode")


def _norm_lon(lon: float) -> float:
    lon = float(lon) % 360.0
    return lon - 360.0 if lon > 180.0 else lon


def _to_ode_lon(lon: float) -> float:
    """ODE expects 0..360 east longitude."""
    return lon + 360.0 if lon < 0 else lon


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
    except (ValueError, TypeError):
        return None
    return f if f > 0 else None


def _parse_time(*values: Any) -> datetime | None:
    for v in values:
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _wkt_polygon_to_geojson(wkt: str) -> dict[str, Any] | None:
    """Parse the first ring of a WKT POLYGON into a lon-normalised GeoJSON polygon."""
    m = re.search(r"\(\(\s*([^()]*?)\s*\)\)", wkt or "")
    if not m:
        return None
    ring: list[list[float]] = []
    for pair in m.group(1).split(","):
        parts = pair.split()
        if len(parts) < 2:
            continue
        try:
            ring.append([_norm_lon(float(parts[0])), float(parts[1])])
        except ValueError:
            continue
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _product_to_row(p: dict[str, Any]) -> Observation | None:
    name = str(p.get("Product_name") or "")
    base = name.split("_", 1)[0].strip().lower()
    if not base:
        return None

    footprint: dict[str, Any] | None = None
    for key in ("Footprint_C0_geometry", "Footprint_geometry", "Footprint_GL_geometry"):
        g = _wkt_polygon_to_geojson(str(p.get(key) or ""))
        if g:
            footprint = g
            break

    if footprint is not None:
        try:
            minx, miny, maxx, maxy = bbox_of(footprint)
        except ValueError:
            footprint = None
    if footprint is None:
        try:
            minx = _norm_lon(float(p["Westernmost_longitude"]))
            maxx = _norm_lon(float(p["Easternmost_longitude"]))
            miny = float(p["Minimum_latitude"])
            maxy = float(p["Maximum_latitude"])
        except (KeyError, ValueError, TypeError):
            return None
        if maxx < minx or maxy < miny:
            return None  # meridian-crossing / malformed — skip
        footprint = polygon_from_bbox((minx, miny, maxx, maxy))

    if not (
        -180 <= minx <= 180 and -180 <= maxx <= 180 and -90 <= miny <= 90 and -90 <= maxy <= 90
    ):
        return None

    try:
        clon = _norm_lon(float(p.get("Center_longitude")))
        clat = float(p.get("Center_latitude"))
    except (ValueError, TypeError):
        clon, clat = (minx + maxx) / 2.0, (miny + maxy) / 2.0

    title = str(p.get("Comment") or "").strip() or f"CRISM MTRDR {base.upper()}"
    now = utcnow()
    return Observation(
        id=base,
        instrument="CRISM",
        product_type="MTRDR",
        title=title[:160],
        provider="PDS Geosciences Node (MRO/CRISM) via ODE",
        region=None,
        center_lon=clon,
        center_lat=clat,
        minx=minx,
        miny=miny,
        maxx=maxx,
        maxy=maxy,
        footprint_geojson=footprint_to_text(footprint),
        acquired_at=_parse_time(p.get("Observation_time"), p.get("UTC_start_time")),
        resolution_m=_safe_float(p.get("Map_scale")),
        analysis_suitable=True,
        thumbnail_url=None,
        dataset_id="crism_mtrdr",
        spectral=None,
        quality={"atmospherically_corrected": True, "photometrically_corrected": True},
        source_url=str(p.get("ProductURL") or p.get("External_url") or ""),
        browse_url=(str(p.get("FilesURL") or "") or None),
        created_at=now,
        updated_at=now,
    )


async def discover_crism_mtrdr(
    bbox: tuple[float, float, float, float], limit: int
) -> list[Observation]:
    """Discover CRISM MTRDR products within ``bbox`` (west,south,east,north deg)."""
    settings = get_settings()
    if not settings.ode_enabled:
        return []
    import httpx

    w, s, e, n = bbox
    params = {
        "query": "product",
        "target": "mars",
        "ihid": "MRO",
        "iid": "CRISM",
        "pt": "MTRDR",
        "results": "m",
        "output": "JSON",
        "westernlon": _to_ode_lon(w),
        "easternlon": _to_ode_lon(e),
        "minlat": s,
        "maxlat": n,
        "pagelength": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ode_timeout_s) as client:
            resp = await client.get(settings.ode_base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 - external service must not 500 us
        _log.warning("ode.query_failed", error=str(exc))
        return []

    container = data.get("ODEResults") or data
    products = container.get("Products") or {}
    plist = products.get("Product") if isinstance(products, dict) else products
    if isinstance(plist, dict):
        plist = [plist]

    rows: dict[str, Observation] = {}
    for p in plist or []:
        if not isinstance(p, dict):
            continue
        row = _product_to_row(p)
        if row is not None and row.id not in rows:
            rows[row.id] = row
        if len(rows) >= limit:
            break
    _log.info("ode.discovered", bbox=f"{w},{s},{e},{n}", count=len(rows))
    return list(rows.values())
