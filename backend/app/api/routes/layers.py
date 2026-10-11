"""Map layer catalogue (Cesium imagery config)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.schemas import LayerListResponse
from app.services import catalog

router = APIRouter()


@router.get("/layers", response_model=None)
async def list_layers(
    session: AsyncSession = Depends(get_session),
    type: str | None = Query(default=None),
    is_base: bool | None = Query(default=None),
    availability: str | None = Query(default=None),
) -> LayerListResponse:
    items = await catalog.list_layers(
        session, layer_type=type, is_base=is_base, availability=availability
    )
    return LayerListResponse(items=items)
