"""SQLModel table definitions — the persistence contract.

Dialect-agnostic by design: footprints are stored as GeoJSON *text* plus
denormalised minx/miny/maxx/maxy columns so viewport/region filtering is a plain
numeric range query on SQLite and PostGIS alike. On PostGIS the Alembic
migration additionally adds a real ``geometry(POLYGON,104905)`` column + GiST
index (populated at seed time) for ``ST_Intersects``; the ORM itself stays
dialect-free. Rich nested contract objects (layer source/style, result rasters,
provenance steps) are stored as JSON documents and rehydrated into the frozen
Pydantic DTOs on read.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Observation(SQLModel, table=True):
    __tablename__ = "observation"

    id: str = Field(primary_key=True)
    instrument: str = Field(index=True)
    product_type: str = Field(index=True)
    title: str
    provider: str
    region: str | None = Field(default=None, index=True)

    center_lon: float
    center_lat: float
    minx: float = Field(index=True)
    miny: float = Field(index=True)
    maxx: float = Field(index=True)
    maxy: float = Field(index=True)

    footprint_geojson: str = Field(sa_column=Column(Text))

    acquired_at: datetime | None = None
    resolution_m: float | None = None
    analysis_suitable: bool = Field(default=True, index=True)
    thumbnail_url: str | None = None

    dataset_id: str | None = None
    spectral: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    quality: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source_url: str = ""
    browse_url: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Mineral(SQLModel, table=True):
    __tablename__ = "mineral"

    id: str = Field(primary_key=True)
    mineral: str
    mineral_class: str = Field(index=True)
    source: str
    source_id: str | None = None
    spectrum_type: str
    resampled_to: str | None = None
    point_count: int
    wavelength_min_nm: float
    wavelength_max_nm: float
    diagnostic_features_nm: list[float] | None = Field(default=None, sa_column=Column(JSON))
    color: str
    description: str | None = None

    wavelength: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    reflectance: list[float] = Field(default_factory=list, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MapLayerRow(SQLModel, table=True):
    __tablename__ = "map_layer"

    id: str = Field(primary_key=True)
    type: str = Field(index=True)
    title: str
    subtitle: str | None = None
    is_base: bool = Field(default=False, index=True)
    default_visible: bool = False
    attribution: str
    sort: int = Field(default=0, index=True)

    source: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    style: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    availability: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    bounds: list[float] | None = Field(default=None, sa_column=Column(JSON))
    legend: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AnalysisJobRow(SQLModel, table=True):
    __tablename__ = "analysis_job"
    __table_args__ = (Index("ix_job_client_created", "client_fingerprint", "created_at"),)

    id: str = Field(primary_key=True)
    observation_id: str = Field(index=True)
    algorithm: str
    reference_id: str
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    status: str = Field(default="queued", index=True)
    progress: float = 0.0
    message: str | None = None
    result_id: str | None = Field(default=None, index=True)
    error: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    client_fingerprint: str = Field(default="anonymous", index=True)
    idempotency_key: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisResultRow(SQLModel, table=True):
    __tablename__ = "analysis_result"

    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    observation_id: str = Field(index=True)
    reference_id: str
    mineral: str
    provenance_id: str = Field(index=True)
    caveat: str

    # Full serialized AnalysisResult DTO (rehydrated on read).
    doc: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    bounds: list[float] = Field(default_factory=list, sa_column=Column(JSON))

    # Internal raster file paths (relative to STORAGE_ROOT/results/<id>).
    angle_path: str | None = None
    mask_path: str | None = None
    score_path: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ProvenanceRow(SQLModel, table=True):
    __tablename__ = "provenance"

    id: str = Field(primary_key=True)
    result_id: str = Field(index=True)
    job_id: str = Field(index=True)
    observation_id: str
    reference_id: str
    doc: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


__all__ = [
    "AnalysisJobRow",
    "AnalysisResultRow",
    "MapLayerRow",
    "Mineral",
    "Observation",
    "ProvenanceRow",
    "utcnow",
]
