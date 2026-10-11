"""MarsGIS shared contract — provenance (reproducibility record) (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .common import ApiModel
from .enums import ProvenanceStepStatus


class SoftwareComponent(ApiModel):
    name: str
    version: str


class ProvenanceStep(ApiModel):
    order: int = Field(ge=0)
    name: str
    software: str
    version: str | None = None
    params: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime
    status: ProvenanceStepStatus
    message: str | None = None


class Provenance(ApiModel):
    id: str
    result_id: str
    job_id: str
    observation_id: str
    reference_id: str
    engine_image: str = Field(description="ghcr.io/<account>/marsgis-engine:<tag>")
    engine_version: str
    software: list[SoftwareComponent] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    steps: list[ProvenanceStep] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    inputs_checksums: dict[str, str] | None = None
    outputs_checksums: dict[str, str] | None = None
    started_at: datetime
    finished_at: datetime
    timestamp: datetime
    caveat: str
