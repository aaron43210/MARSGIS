"""Spectral reference ('minerals') endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.errors import NotFoundError
from app.schemas import MineralListResponse
from app.schemas.spectral import SpectralReference
from app.services import catalog

router = APIRouter()


@router.get("/minerals", response_model=None)
async def list_minerals(
    session: AsyncSession = Depends(get_session),
    mineral_class: str | None = Query(default=None, alias="class"),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> MineralListResponse:
    items = await catalog.list_minerals(session, mineral_class=mineral_class, source=source, q=q)
    return MineralListResponse(items=items)


@router.get("/minerals/{mineral_id}", response_model=None)
async def get_mineral(
    mineral_id: str,
    session: AsyncSession = Depends(get_session),
) -> SpectralReference:
    row = await catalog.get_mineral_row(session, mineral_id)
    if row is None:
        raise NotFoundError(f"mineral '{mineral_id}' not found")
    return catalog.mineral_full(row)
