"""MarsGIS shared contract — spectral reference library ('minerals') (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ApiModel
from .enums import MineralClass, SpectrumType


class SpectralReferenceSummary(ApiModel):
    id: str = Field(description="slug, e.g. 'mica_carbonate_calcite'")
    mineral: str
    mineral_class: MineralClass
    source: str
    source_id: str | None = None
    spectrum_type: SpectrumType
    resampled_to: str | None = None
    point_count: int = Field(ge=2)
    wavelength_min_nm: float
    wavelength_max_nm: float
    diagnostic_features_nm: list[float] | None = None
    color: str = Field(pattern=r"^#(?:[0-9a-fA-F]{6})$")
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class SpectralReference(SpectralReferenceSummary):
    wavelength_unit: Literal["nm"] = "nm"
    wavelength: list[float] = Field(description="Ascending; same length as reflectance.")
    reflectance: list[float]

    @model_validator(mode="after")
    def _check_lengths(self) -> SpectralReference:
        if len(self.wavelength) != len(self.reflectance):
            raise ValueError("wavelength and reflectance must have equal length")
        if len(self.wavelength) != self.point_count:
            raise ValueError("point_count must equal len(wavelength)")
        return self
