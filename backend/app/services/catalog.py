"""Catalogue + reference query helpers (keep route handlers thin)."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.geo import bbox_overlap_clause, footprint_from_text
from app.db.models import MapLayerRow, Mineral, Observation
from app.schemas import (
    LayerAvailability,
    LayerSource,
    LayerStyle,
    Legend,
    MapLayer,
    ObservationSummary,
    SpectralReference,
    SpectralReferenceSummary,
)
from app.schemas import (
    Observation as ObservationDTO,
)

_SORT_COLUMNS = {
    "acquired_at": Observation.acquired_at,
    "id": Observation.id,
    "resolution_m": Observation.resolution_m,
}


# --------------------------------------------------------------------------- #
# Converters: ORM row -> frozen Pydantic DTO
# --------------------------------------------------------------------------- #
def observation_summary(row: Observation) -> ObservationSummary:
    return ObservationSummary(
        id=row.id,
        instrument=row.instrument,
        product_type=row.product_type,
        title=row.title,
        provider=row.provider,
        region=row.region,
        bbox=(row.minx, row.miny, row.maxx, row.maxy),
        center={"lon": row.center_lon, "lat": row.center_lat},
        footprint=footprint_from_text(row.footprint_geojson),
        acquired_at=row.acquired_at,
        resolution_m=row.resolution_m,
        analysis_suitable=row.analysis_suitable,
        thumbnail_url=row.thumbnail_url,
    )


def observation_full(row: Observation) -> ObservationDTO:
    return ObservationDTO(
        id=row.id,
        instrument=row.instrument,
        product_type=row.product_type,
        title=row.title,
        provider=row.provider,
        region=row.region,
        bbox=(row.minx, row.miny, row.maxx, row.maxy),
        center={"lon": row.center_lon, "lat": row.center_lat},
        footprint=footprint_from_text(row.footprint_geojson),
        acquired_at=row.acquired_at,
        resolution_m=row.resolution_m,
        analysis_suitable=row.analysis_suitable,
        thumbnail_url=row.thumbnail_url,
        target="Mars",
        dataset_id=row.dataset_id,
        spectral=row.spectral,
        quality=row.quality or {},
        source_url=row.source_url,
        browse_url=row.browse_url,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def mineral_summary(row: Mineral) -> SpectralReferenceSummary:
    return SpectralReferenceSummary(
        id=row.id,
        mineral=row.mineral,
        mineral_class=row.mineral_class,
        source=row.source,
        source_id=row.source_id,
        spectrum_type=row.spectrum_type,
        resampled_to=row.resampled_to,
        point_count=row.point_count,
        wavelength_min_nm=row.wavelength_min_nm,
        wavelength_max_nm=row.wavelength_max_nm,
        diagnostic_features_nm=row.diagnostic_features_nm,
        color=row.color,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def mineral_full(row: Mineral) -> SpectralReference:
    return SpectralReference(
        id=row.id,
        mineral=row.mineral,
        mineral_class=row.mineral_class,
        source=row.source,
        source_id=row.source_id,
        spectrum_type=row.spectrum_type,
        resampled_to=row.resampled_to,
        point_count=row.point_count,
        wavelength_min_nm=row.wavelength_min_nm,
        wavelength_max_nm=row.wavelength_max_nm,
        diagnostic_features_nm=row.diagnostic_features_nm,
        color=row.color,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        wavelength=row.wavelength,
        reflectance=row.reflectance,
    )


def map_layer(row: MapLayerRow) -> MapLayer:
    return MapLayer(
        id=row.id,
        type=row.type,
        title=row.title,
        subtitle=row.subtitle,
        is_base=row.is_base,
        default_visible=row.default_visible,
        source=LayerSource.model_validate(row.source),
        style=LayerStyle.model_validate(row.style),
        attribution=row.attribution,
        availability=LayerAvailability.model_validate(row.availability),
        bounds=tuple(row.bounds) if row.bounds else None,
        legend=Legend.model_validate(row.legend) if row.legend else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
async def list_observations(
    session: AsyncSession,
    *,
    instrument: str | None = None,
    product_type: str | None = None,
    region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    suitable: bool | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "-acquired_at",
) -> tuple[list[ObservationSummary], int]:
    where = []
    if instrument:
        where.append(Observation.instrument == instrument)
    if product_type:
        where.append(Observation.product_type == product_type)
    if region:
        where.append(Observation.region == region)
    if suitable is not None:
        where.append(Observation.analysis_suitable == suitable)
    if bbox is not None:
        where.append(bbox_overlap_clause(bbox))
    if q:
        pattern = f"%{q.lower()}%"
        where.append(
            or_(
                func.lower(Observation.id).like(pattern),
                func.lower(Observation.title).like(pattern),
            )
        )

    count_stmt = select(func.count()).select_from(Observation)
    data_stmt = select(Observation)
    for clause in where:
        count_stmt = count_stmt.where(clause)
        data_stmt = data_stmt.where(clause)

    desc = sort.startswith("-")
    key = sort[1:] if desc else sort
    col = _SORT_COLUMNS.get(key, Observation.acquired_at)
    data_stmt = data_stmt.order_by(col.desc() if desc else col.asc(), Observation.id.asc())
    data_stmt = data_stmt.limit(limit).offset(offset)

    total = int((await session.execute(count_stmt)).scalar_one())
    rows = (await session.execute(data_stmt)).scalars().all()
    return [observation_summary(r) for r in rows], total


async def get_observation_row(session: AsyncSession, obs_id: str) -> Observation | None:
    row = await session.get(Observation, obs_id)
    if row is not None:
        return row
    # Provider ids are stored verbatim; be tolerant of case for lookups.
    stmt = select(Observation).where(func.lower(Observation.id) == obs_id.lower())
    return (await session.execute(stmt)).scalars().first()


async def list_minerals(
    session: AsyncSession,
    *,
    mineral_class: str | None = None,
    source: str | None = None,
    q: str | None = None,
) -> list[SpectralReferenceSummary]:
    stmt = select(Mineral)
    if mineral_class:
        stmt = stmt.where(Mineral.mineral_class == mineral_class)
    if source:
        stmt = stmt.where(Mineral.source == source)
    if q:
        stmt = stmt.where(func.lower(Mineral.mineral).like(f"%{q.lower()}%"))
    # carbonate first, then olivine/clay, then the rest.
    stmt = stmt.order_by(Mineral.mineral_class.asc(), Mineral.id.asc())
    rows = (await session.execute(stmt)).scalars().all()
    carbonate_first = sorted(
        rows, key=lambda r: (r.mineral_class != "carbonate", r.mineral_class, r.id)
    )
    return [mineral_summary(r) for r in carbonate_first]


async def get_mineral_row(session: AsyncSession, mineral_id: str) -> Mineral | None:
    return await session.get(Mineral, mineral_id)


async def list_layers(
    session: AsyncSession,
    *,
    layer_type: str | None = None,
    is_base: bool | None = None,
    availability: str | None = None,
) -> list[MapLayer]:
    stmt = select(MapLayerRow)
    if layer_type:
        stmt = stmt.where(MapLayerRow.type == layer_type)
    if is_base is not None:
        stmt = stmt.where(MapLayerRow.is_base == is_base)
    stmt = stmt.order_by(MapLayerRow.sort.asc(), MapLayerRow.id.asc())
    rows = (await session.execute(stmt)).scalars().all()
    layers = [map_layer(r) for r in rows]
    if availability:
        layers = [ml for ml in layers if ml.availability.status == availability]
    return layers
