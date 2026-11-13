"""MarsGIS shared contract — analysis jobs & results (Pydantic v2)."""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import Field

from .common import ApiModel, BBox, LonLat
from .enums import AnalysisAlgorithm, AssetRole, JobStatus
from .layer import Legend, MapLayer

_COG_MEDIA = "image/tiff; application=geotiff; profile=cloud-optimized"


class SamParams(ApiModel):
    """SAM parameters; all optional so create bodies may send a subset."""

    threshold_rad: float = Field(default=0.10, gt=0.0, le=math.pi / 2)
    continuum_removed: bool = False
    wavelength_subset_nm: tuple[float, float] | None = (1000.0, 2600.0)
    bands: list[int] | None = None
    output_resolution_m: float | None = Field(default=None, gt=0.0)


AnalysisParams = SamParams  # v1: SAM only


class AnalysisJobCreate(ApiModel):
    observation_id: str
    algorithm: AnalysisAlgorithm = AnalysisAlgorithm.SAM
    reference_id: str
    params: SamParams | None = None
    #: Optional point inside the observation footprint. When set, the analysed window
    #: is centred here (the spot the user clicked) instead of the observation centre.
    center: LonLat | None = None


class JobError(ApiModel):
    code: str
    message: str
    detail: str | None = None
    retriable: bool = False


class AnalysisJob(ApiModel):
    id: str
    observation_id: str
    algorithm: AnalysisAlgorithm
    reference_id: str
    params: SamParams
    #: The analysis centre the job was created with (None = observation centre).
    center: LonLat | None = None
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None
    result_id: str | None = None
    error: JobError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RasterAsset(ApiModel):
    href: str
    role: AssetRole
    media_type: str = _COG_MEDIA
    units: str
    value_range: tuple[float, float] | None = None
    nodata: float | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None


class ResultRasters(ApiModel):
    cog: RasterAsset
    angle: RasterAsset
    mask: RasterAsset
    score: RasterAsset | None = None


class Histogram(ApiModel):
    bin_edges: list[float]
    counts: list[int]


class SummaryStats(ApiModel):
    pixel_count: int = Field(ge=0)
    valid_pixel_count: int = Field(ge=0)
    detected_pixel_count: int = Field(ge=0)
    detected_fraction: float = Field(ge=0.0, le=1.0)
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    threshold_rad: float
    reference_id: str
    mineral: str
    histogram: Histogram | None = None
    caveat: str


class AnalysisResult(ApiModel):
    id: str
    job_id: str
    observation_id: str
    algorithm: AnalysisAlgorithm
    reference_id: str
    mineral: str
    rasters: ResultRasters
    bounds: BBox
    value_range: tuple[float, float]
    legend: Legend
    summary_stats: SummaryStats
    map_layer: MapLayer
    provenance_id: str
    caveat: str
    #: True when the input was the bundled SYNTHETIC sample cube, not the selected
    #: observation. The UI must say so next to the result.
    synthetic_input: bool = False
    created_at: datetime
    updated_at: datetime


class ResultPixel(ApiModel):
    """The real spectrum and spectral angle of one result pixel (pixel inspector)."""

    result_id: str
    observation_id: str
    mineral: str
    lon: float
    lat: float
    inside: bool
    row: int | None = None
    col: int | None = None
    angle_rad: float | None = None
    raster_angle_rad: float | None = None
    threshold_rad: float | None = None
    is_candidate: bool | None = None
    continuum_removed: bool | None = None
    wavelength_nm: list[float] = []
    pixel: list[float | None] = []
    reference: list[float] = []
    synthetic_input: bool
