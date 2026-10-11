"""Observation catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.geo import parse_bbox
from app.db.session import session_scope
from app.deps import get_session
from app.errors import NotFoundError, ValidationErrorApp
from app.schemas import ObservationListResponse
from app.schemas.observation import Observation as ObservationDTO
from app.services import catalog, ode

router = APIRouter()


@router.get("/observations/discover", response_model=None, include_in_schema=False)
async def discover_observations(
    bbox: str = Query(..., description="west,south,east,north (Mars degrees)"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Live whole-Mars discovery: query PDS ODE for CRISM MTRDR products in the
    given bbox, merge new ones into the catalogue (idempotent), and return them.
    Additive to the frozen contract (not in /openapi.json)."""
    try:
        bbox_t = parse_bbox(bbox)
    except ValueError as exc:
        raise ValidationErrorApp(str(exc)) from exc
    if bbox_t is None:
        raise ValidationErrorApp("bbox is required (west,south,east,north)")

    settings = get_settings()
    limit = min(limit, settings.discover_max_results)
    rows = await ode.discover_crism_mtrdr(bbox_t, limit)
    # Build summaries BEFORE the rows are attached to a session (avoids expiry).
    items = [catalog.observation_summary(r).model_dump(mode="json") for r in rows]
    added = 0
    if rows:
        async with session_scope() as session:
            added = await catalog.upsert_observations(session, rows)
    return {
        "items": items,
        "discovered": len(items),
        "added": added,
        "source": "PDS Orbital Data Explorer (ODE) — CRISM MTRDR",
    }


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
