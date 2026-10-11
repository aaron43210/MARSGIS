"""MarsGIS shared contract — common primitive & envelope schemas (Pydantic v2)."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for every wire model: reject unknown fields, allow field aliases."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True)


#: [west, south, east, north] in Mars IAU 2000 degrees (lon [-180,180], lat [-90,90]).
#: NOT Earth WGS84 — see contracts/enums.json#crs.
BBox = tuple[float, float, float, float]


class LonLat(ApiModel):
    lon: float = Field(ge=-180.0, le=180.0)
    lat: float = Field(ge=-90.0, le=90.0)


class GeoJSONPolygon(ApiModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class GeoJSONMultiPolygon(ApiModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[list[float]]]]


Footprint = Union[GeoJSONPolygon, GeoJSONMultiPolygon]


class Paginated(ApiModel, Generic[T]):
    """Uniform list envelope for every collection endpoint."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class FieldError(ApiModel):
    field: str
    message: str


class ErrorResponse(ApiModel):
    """Uniform error body for every non-2xx response (incl. 422 validation)."""

    code: str
    message: str
    detail: str | None = None
    request_id: str | None = None
    errors: list[FieldError] | None = None
