"""Result metadata + GeoTIFF download."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AnalysisResultRow, Mineral, ProvenanceRow
from app.deps import get_session
from app.errors import NotFoundError, ValidationErrorApp
from app.schemas import AnalysisResult, ResultPixel
from app.services import pixel, storage
from app.services.jobs.tasks import local_cube_path

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


@router.get("/results/{result_id}/pixel", response_model=None)
async def get_result_pixel(
    result_id: str,
    lon: float = Query(ge=-180.0, le=180.0),
    lat: float = Query(ge=-90.0, le=90.0),
    session: AsyncSession = Depends(get_session),
) -> ResultPixel:
    """The real spectrum and spectral angle of the result pixel under lon/lat."""
    row = await load_result_row(session, result_id)
    if not row.angle_path:
        raise NotFoundError(f"result '{result_id}' has no raster")
    prov = await session.get(ProvenanceRow, row.provenance_id)
    params = ((prov.doc or {}).get("params") or {}) if prov else {}
    cube_source = str(params.get("cube_source") or "sample")
    raw_c = params.get("center")
    center = (float(raw_c["lon"]), float(raw_c["lat"])) if isinstance(raw_c, dict) else None
    area = str(params.get("area") or "small")
    cube = local_cube_path(get_settings(), row.observation_id, cube_source, center, area)
    if cube is None:
        raise NotFoundError(
            "the image this result was computed from is no longer on this server",
            detail="Run the analysis again to inspect its pixels.",
        )
    mineral = await session.get(Mineral, row.reference_id)
    if mineral is None:
        raise NotFoundError(f"mineral '{row.reference_id}' not found")
    angle_path = storage.safe_path(result_id, row.angle_path)
    summary = (row.doc or {}).get("summary_stats") or {}
    threshold = float(params.get("threshold_rad") or summary.get("threshold_rad") or 0.10)
    result = await anyio.to_thread.run_sync(
        lambda: pixel.inspect(
            cube_path=cube,
            angle_path=angle_path,
            mineral_class=mineral.mineral_class,
            lon=lon,
            lat=lat,
            threshold_rad=threshold,
            continuum_removed=bool(params.get("continuum_removed", False)),
            wavelength_subset_nm=params.get("wavelength_subset_nm"),
        )
    )
    result["result_id"] = result_id
    result["observation_id"] = row.observation_id
    result["mineral"] = row.mineral
    result["synthetic_input"] = cube_source == "sample"
    return ResultPixel.model_validate(result)
