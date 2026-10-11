"""MarsGIS shared contract — health, query params, response envelopes (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import Field

from .analysis import AnalysisJob
from .common import ApiModel, Paginated
from .enums import (
    AvailabilityStatus,
    HealthStatus,
    InstrumentType,
    JobStatus,
    LayerType,
    MineralClass,
    ProductType,
)
from .layer import MapLayer
from .observation import ObservationSummary
from .spectral import SpectralReferenceSummary

T = TypeVar("T")


class HealthComponent(ApiModel):
    status: HealthStatus
    detail: str | None = None
    latency_ms: float | None = None


class HealthComponents(ApiModel):
    db: HealthComponent
    engine: HealthComponent
    tiler: HealthComponent
    queue: HealthComponent


class HealthResponse(ApiModel):
    status: HealthStatus
    version: str
    contract_version: str = "1.0.0"
    git_sha: str | None = None
    time: datetime
    components: HealthComponents
    implemented_algorithms: list[str] = Field(default_factory=lambda: ["SAM"])


class ObservationQuery(ApiModel):
    """GET /api/observations query. `bbox` arrives as 'west,south,east,north'."""

    instrument: InstrumentType | None = None
    product_type: ProductType | None = None
    region: str | None = None
    bbox: str | None = Field(default=None, description="west,south,east,north")
    suitable: bool | None = None
    q: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort: Literal["acquired_at", "-acquired_at", "id", "resolution_m", "-resolution_m"] = (
        "-acquired_at"
    )


class MineralQuery(ApiModel):
    mineral_class: MineralClass | None = Field(default=None, alias="class")
    source: str | None = None
    q: str | None = None


class JobQuery(ApiModel):
    status: JobStatus | None = None
    observation_id: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class LayerQuery(ApiModel):
    type: LayerType | None = None
    is_base: bool | None = None
    availability: AvailabilityStatus | None = None


class ListResponse(ApiModel, Generic[T]):
    items: list[T]


LayerListResponse = ListResponse[MapLayer]
MineralListResponse = ListResponse[SpectralReferenceSummary]
ObservationListResponse = Paginated[ObservationSummary]
JobListResponse = Paginated[AnalysisJob]
