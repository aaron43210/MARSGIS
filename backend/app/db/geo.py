"""Dialect-aware footprint / bbox helpers.

Footprints are kept as GeoJSON text everywhere; spatial filtering is a numeric
bbox-overlap predicate on SQLite (and a correct, index-free default on PostGIS)
and upgrades to ``ST_Intersects`` against the PostGIS geometry column when the
``geom`` column exists.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.sql import ColumnElement

from app.db.models import Observation


def parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """Parse a 'west,south,east,north' query string into a bbox tuple."""
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be 'west,south,east,north'")
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError as exc:
        raise ValueError("bbox values must be numbers") from exc
    if not (-180.0 <= w <= 180.0 and -180.0 <= e <= 180.0):
        raise ValueError("bbox longitudes must be in [-180, 180]")
    if not (-90.0 <= s <= 90.0 and -90.0 <= n <= 90.0):
        raise ValueError("bbox latitudes must be in [-90, 90]")
    if e < w or n < s:
        raise ValueError("bbox must have east>=west and north>=south")
    return (w, s, e, n)


def bbox_of(geojson: dict[str, Any]) -> tuple[float, float, float, float]:
    """Compute [minx, miny, maxx, maxy] of a GeoJSON Polygon/MultiPolygon."""
    xs: list[float] = []
    ys: list[float] = []

    def _walk(coords: Any) -> None:
        if (
            isinstance(coords, (list, tuple))
            and len(coords) >= 2
            and all(isinstance(c, (int, float)) for c in coords[:2])
        ):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
            return
        if isinstance(coords, (list, tuple)):
            for c in coords:
                _walk(c)

    _walk(geojson.get("coordinates", []))
    if not xs or not ys:
        raise ValueError("geometry has no coordinates")
    return (min(xs), min(ys), max(xs), max(ys))


def polygon_from_bbox(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Build a closed rectangular GeoJSON Polygon from a bbox (degrees)."""
    w, s, e, n = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }


def footprint_to_text(geojson: dict[str, Any]) -> str:
    return json.dumps(geojson, separators=(",", ":"))


def footprint_from_text(raw: str) -> dict[str, Any]:
    return json.loads(raw)


def bbox_overlap_clause(bbox: tuple[float, float, float, float]) -> ColumnElement[bool]:
    """Numeric bbox-overlap predicate (works on every dialect)."""
    w, s, e, n = bbox
    return (
        (Observation.maxx >= w)
        & (Observation.minx <= e)
        & (Observation.maxy >= s)
        & (Observation.miny <= n)
    )
