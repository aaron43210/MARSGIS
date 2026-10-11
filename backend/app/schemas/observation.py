"""MarsGIS shared contract — observations & datasets (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import ApiModel, BBox, Footprint, LonLat
from .enums import DatasetKind, InstrumentType, ProductType, ServiceType


class WavelengthRange(ApiModel):
    detector: str
    min_nm: float
    max_nm: float


class SpectralSummary(ApiModel):
    band_count: int = Field(ge=1)
    wavelength_min_nm: float
    wavelength_max_nm: float
    wavelength_unit: Literal["nm"] = "nm"
    sampling_nm: float | None = None
    ranges: list[WavelengthRange] = Field(default_factory=list)


class QualityFlags(ApiModel):
    has_known_artifacts: bool = False
    spike_corrected: bool = False
    atmospherically_corrected: bool = False
    photometrically_corrected: bool = False
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None


class TemporalExtent(ApiModel):
    start: datetime | None = None
    end: datetime | None = None


class DatasetAccess(ApiModel):
    service: ServiceType
    url: str
    auth_required: bool = False
    notes: str | None = None


class Dataset(ApiModel):
    id: str
    title: str
    description: str | None = None
    provider: str
    kind: DatasetKind
    instrument: InstrumentType | None = None
    product_type: ProductType | None = None
    spatial_extent: BBox | None = None
    temporal_extent: TemporalExtent | None = None
    license: str | None = None
    attribution: str
    access: DatasetAccess
    observation_count: int | None = Field(default=None, ge=0)
    created_at: datetime
    updated_at: datetime


class ObservationSummary(ApiModel):
    id: str = Field(description="Native observation id, e.g. 'FRT00003E12'")
    instrument: InstrumentType
    product_type: ProductType
    title: str
    provider: str
    region: str | None = None
    bbox: BBox
    center: LonLat
    footprint: Footprint
    acquired_at: datetime | None = None
    resolution_m: float | None = Field(default=None, gt=0.0)
    analysis_suitable: bool
    thumbnail_url: str | None = None


class Observation(ObservationSummary):
    target: Literal["Mars"] = "Mars"
    dataset_id: str | None = None
    spectral: SpectralSummary | None = None
    quality: QualityFlags
    source_url: str = Field(
        description="Service URL to fetch/describe the product (not a bulk archive)."
    )
    browse_url: str | None = None
    created_at: datetime
    updated_at: datetime
