"""Cursor elevation read-out: GET /api/elevation?lon=&lat= -> MOLA height (m).

Not part of the frozen v1 OpenAPI contract (include_in_schema=False), so adding
it does not change /openapi.json. Returns elevation_m=null (HTTP 200) when the
point is nodata/out-of-range or the remote DEM is unreachable, so the footer
read-out degrades gracefully.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Query

from app.services.elevation import sample_elevation

router = APIRouter()


@router.get("/elevation", include_in_schema=False)
async def get_elevation(
    lon: float = Query(..., ge=-180.0, le=180.0),
    lat: float = Query(..., ge=-90.0, le=90.0),
) -> dict:
    elevation = await anyio.to_thread.run_sync(sample_elevation, lon, lat)
    return {
        "lon": lon,
        "lat": lat,
        "elevation_m": elevation,
        "datum": "Mars IAU 2000 sphere (3396190 m)",
        "source": "MOLA 463 m global DEM",
    }
