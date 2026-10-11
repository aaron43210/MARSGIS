"""Result metadata + GeoTIFF download."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisResultRow
from app.deps import get_session
from app.errors import NotFoundError, ValidationErrorApp
from app.schemas import AnalysisResult
from app.services import storage

router = APIRouter()

_COG_MEDIA = "image/tiff; application=geotiff; profile=cloud-optimized"
_ASSET_TO_FIELD = {
    "primary_metric": "angle_path",
    "sam_angle": "angle_path",
    "detection_mask": "mask_path",
    "match_score": "score_path",
}


async def load_result_row(session: AsyncSession, result_id: str) -> AnalysisResultRow:
    row = await session.get(AnalysisResultRow, result_id)
    if row is None:
        raise NotFoundError(f"result '{result_id}' not found")
    return row


@router.get("/results/{result_id}", response_model=None)
async def get_result(
    result_id: str,
    session: AsyncSession = Depends(get_session),
) -> AnalysisResult:
    row = await load_result_row(session, result_id)
    return AnalysisResult.model_validate(row.doc)


@router.get("/results/{result_id}/download", response_model=None)
async def download_result(
    result_id: str,
    session: AsyncSession = Depends(get_session),
    asset: str = Query(default="primary_metric"),
) -> FileResponse:
    row = await load_result_row(session, result_id)
    field = _ASSET_TO_FIELD.get(asset)
    if field is None:
        raise ValidationErrorApp(
            f"unknown asset '{asset}'",
            detail=f"Valid assets: {sorted(_ASSET_TO_FIELD)}.",
        )
    name: str | None = getattr(row, field)
    if not name:
        raise NotFoundError(f"result '{result_id}' has no '{asset}' asset")
    path = storage.safe_path(result_id, name)
    filename = f"{result_id}_{asset}.tif"
    return FileResponse(
        path,
        media_type=_COG_MEDIA,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
