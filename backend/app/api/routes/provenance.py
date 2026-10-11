"""Reproducibility record (provenance) endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProvenanceRow
from app.deps import get_session
from app.errors import NotFoundError
from app.schemas import Provenance

router = APIRouter()


@router.get("/provenance/{provenance_id}", response_model=None)
async def get_provenance(
    provenance_id: str,
    session: AsyncSession = Depends(get_session),
) -> Provenance:
    row = await session.get(ProvenanceRow, provenance_id)
    if row is None:
        raise NotFoundError(f"provenance '{provenance_id}' not found")
    return Provenance.model_validate(row.doc)
