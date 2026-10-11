"""On-the-fly result raster tiling for Cesium (Mars geographic TMS)."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.colormaps import parse_rescale
from app.core.constants import MAX_ZOOM, SAM_ANGLE_COLORMAP
from app.db.models import AnalysisResultRow
from app.deps import get_session
from app.errors import NotFoundError, ValidationErrorApp
from app.services import raster, storage

router = APIRouter()

_IMMUTABLE = "public, max-age=31536000, immutable"


async def _result_angle(session: AsyncSession, result_id: str) -> tuple[AnalysisResultRow, str]:
    row = await session.get(AnalysisResultRow, result_id)
    if row is None:
        raise NotFoundError(f"result '{result_id}' not found")
    if not row.angle_path:
        raise NotFoundError(f"result '{result_id}' has no raster")
    return row, row.angle_path


def _value_range(row: AnalysisResultRow, rescale: str | None) -> tuple[float, float]:
    override = parse_rescale(rescale)
    if override is not None:
        return override
    vr = (row.doc or {}).get("value_range")
    if isinstance(vr, (list, tuple)) and len(vr) == 2:
        return (float(vr[0]), float(vr[1]))
    return (0.0, 0.10)


def _validate_zxy(z: int, x: int, y: int) -> None:
    if z < 0 or z > MAX_ZOOM:
        raise ValidationErrorApp(f"z out of range [0, {MAX_ZOOM}]")
    max_x = 2 * (2**z)  # 2 columns at z0
    max_y = 1 * (2**z)  # 1 row at z0
    if not (0 <= x < max_x) or not (0 <= y < max_y):
        raise ValidationErrorApp("tile x/y out of range for this zoom")


@router.get("/results/{result_id}/tiles/{z}/{x}/{y}.png", response_model=None)
async def get_result_tile(
    result_id: str,
    z: int,
    x: int,
    y: int,
    session: AsyncSession = Depends(get_session),
    colormap: str | None = Query(default=None),
    rescale: str | None = Query(default=None),
) -> Response:
    _validate_zxy(z, x, y)
    row, angle_name = await _result_angle(session, result_id)
    path = storage.safe_path(result_id, angle_name)
    value_range = _value_range(row, rescale)
    cmap = colormap or SAM_ANGLE_COLORMAP

    png = await anyio.to_thread.run_sync(
        lambda: raster.tile(path, z, x, y, value_range=value_range, colormap_name=cmap)
    )
    if png is None:
        return Response(status_code=204)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": _IMMUTABLE})


@router.get("/results/{result_id}/preview.png", include_in_schema=False)
async def get_result_preview(
    result_id: str,
    session: AsyncSession = Depends(get_session),
    colormap: str | None = Query(default=None),
    rescale: str | None = Query(default=None),
    max_size: int = Query(default=1024, ge=16, le=2048),
) -> Response:
    row, angle_name = await _result_angle(session, result_id)
    path = storage.safe_path(result_id, angle_name)
    value_range = _value_range(row, rescale)
    cmap = colormap or SAM_ANGLE_COLORMAP

    png = await anyio.to_thread.run_sync(
        lambda: raster.preview(path, value_range=value_range, colormap_name=cmap, max_size=max_size)
    )
    return Response(content=png, media_type="image/png", headers={"Cache-Control": _IMMUTABLE})
