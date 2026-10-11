"""Observation catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.geo import parse_bbox
from app.deps import get_session
from app.errors import NotFoundError, ValidationErrorApp
from app.schemas import ObservationListResponse
from app.schemas.observation import Observation as ObservationDTO
from app.services import catalog

router = APIRouter()


@router.get("/observations", response_model=None)
async def list_observations(
    session: AsyncSession = Depends(get_session),
    instrument: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    region: str | None = Query(default=None),
    bbox: str | None = Query(default=None, description="west,south,east,north"),
    suitable: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="-acquired_at"),
) -> ObservationListResponse:
    try:
        bbox_t = parse_bbox(bbox)
    except ValueError as exc:
        raise ValidationErrorApp(str(exc)) from exc

    items, total = await catalog.list_observations(
        session,
        instrument=instrument,
        product_type=product_type,
        region=region,
        bbox=bbox_t,
        suitable=suitable,
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    next_offset = offset + limit if (offset + limit) < total else None
    return ObservationListResponse(
        items=items, total=total, limit=limit, offset=offset, next_offset=next_offset
    )


@router.get("/observations/{obs_id}", response_model=None)
async def get_observation(
    obs_id: str,
    session: AsyncSession = Depends(get_session),
) -> ObservationDTO:
    row = await catalog.get_observation_row(session, obs_id)
    if row is None:
        raise NotFoundError(f"observation '{obs_id}' not found")
    return catalog.observation_full(row)
