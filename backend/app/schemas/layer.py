"""MarsGIS shared contract — map layers, tile sources, legends (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import ApiModel, BBox
from .enums import AvailabilityStatus, LayerType, LegendType, TileOrder, TilingScheme


class LayerSource(ApiModel):
    url_template: str
    tiling_scheme: TilingScheme = TilingScheme.geographic
    tile_order: TileOrder
    tile_size: int = 256
    file_extension: Literal["jpg", "png"]
    level_zero_tiles_x: int = 2
    level_zero_tiles_y: int = 1
    min_zoom: int = 0
    max_zoom: int
    subdomains: list[str] | None = None
    tile_matrix_set: str | None = None
    request_headers: dict[str, str] | None = None
    provider: str


class LayerStyle(ApiModel):
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    colormap: str | None = None
    value_range: tuple[float, float] | None = None
    z_index: int = 0


class LayerAvailability(ApiModel):
    status: AvailabilityStatus
    checked_at: datetime | None = None
    sample_tile_url: str | None = None
    http_status: int | None = None
    note: str | None = None


class LegendStop(ApiModel):
    value: float | None = None
    color: str
    label: str


class Legend(ApiModel):
    title: str
    type: LegendType
    colormap: str | None = None
    value_range: tuple[float, float] | None = None
    units: str | None = None
    stops: list[LegendStop] = Field(default_factory=list)
    nodata_label: str | None = None
    caveat: str | None = None


class MapLayer(ApiModel):
    id: str
    type: LayerType
    title: str
    subtitle: str | None = None
    is_base: bool = False
    default_visible: bool = False
    source: LayerSource
    style: LayerStyle
    attribution: str
    availability: LayerAvailability
    bounds: BBox | None = None
    legend: Legend | None = None
    created_at: datetime
    updated_at: datetime
