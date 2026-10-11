"""MarsGIS shared contract — canonical enumerations.

MIRROR of contracts/enums.json. Do not edit one without the other.
contract_version: 1.0.0
"""

from __future__ import annotations

from enum import Enum


class InstrumentType(str, Enum):
    CRISM = "CRISM"
    CTX = "CTX"
    HiRISE = "HiRISE"
    HRSC = "HRSC"
    OMEGA = "OMEGA"
    THEMIS = "THEMIS"
    MOLA = "MOLA"


class ProductType(str, Enum):
    MTRDR = "MTRDR"
    TRDR = "TRDR"
    DDR = "DDR"
    MOSAIC = "MOSAIC"
    DEM = "DEM"
    ORTHOIMAGE = "ORTHOIMAGE"
    BASEMAP = "BASEMAP"


class AnalysisAlgorithm(str, Enum):
    SAM = "SAM"
    SID = "SID"
    BAND_RATIO = "BAND_RATIO"


#: Algorithms whose engine implementation is guaranteed in v1; others -> HTTP 422.
IMPLEMENTED_ALGORITHMS_V1: tuple[AnalysisAlgorithm, ...] = (AnalysisAlgorithm.SAM,)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


#: Allowed job state transitions. Terminal states have no outgoing edges.
JOB_STATUS_TRANSITIONS: dict[JobStatus, tuple[JobStatus, ...]] = {
    JobStatus.queued: (JobStatus.running, JobStatus.failed),
    JobStatus.running: (JobStatus.succeeded, JobStatus.failed),
    JobStatus.succeeded: (),
    JobStatus.failed: (),
}
TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset({JobStatus.succeeded, JobStatus.failed})


class LayerType(str, Enum):
    basemap = "basemap"
    wmts = "wmts"
    xyz = "xyz"
    result_tiles = "result_tiles"
    geojson_overlay = "geojson_overlay"


class TilingScheme(str, Enum):
    geographic = "geographic"
    mercator = "mercator"


class TileOrder(str, Enum):
    zyx = "zyx"
    zxy = "zxy"


class MineralClass(str, Enum):
    carbonate = "carbonate"
    olivine = "olivine"
    phyllosilicate = "phyllosilicate"
    pyroxene = "pyroxene"
    sulfate = "sulfate"
    iron_oxide = "iron_oxide"
    hydrated_silica = "hydrated_silica"
    other = "other"


class AvailabilityStatus(str, Enum):
    verified = "verified"
    unconfirmed = "unconfirmed"
    unavailable = "unavailable"


class AssetRole(str, Enum):
    primary_metric = "primary_metric"
    sam_angle = "sam_angle"
    detection_mask = "detection_mask"
    match_score = "match_score"


class LegendType(str, Enum):
    continuous = "continuous"
    categorical = "categorical"


class SpectrumType(str, Enum):
    reflectance = "reflectance"
    continuum_removed = "continuum_removed"


class HealthStatus(str, Enum):
    ok = "ok"
    degraded = "degraded"
    down = "down"


class ProvenanceStepStatus(str, Enum):
    succeeded = "succeeded"
    failed = "failed"


class DatasetKind(str, Enum):
    observation_collection = "observation_collection"
    mosaic = "mosaic"
    dem = "dem"
    basemap = "basemap"
    reference_library = "reference_library"


class ServiceType(str, Enum):
    WMTS = "WMTS"
    WMS = "WMS"
    XYZ = "XYZ"
    REST = "REST"
    STAC = "STAC"
    LOCAL = "LOCAL"


#: Candidate-not-confirmed caveat. MUST accompany every rendered detection result.
CANDIDATE_MATCH_CAVEAT = (
    "Candidate spectral match (SAM angle below threshold). NOT a confirmed mineral "
    "deposit; requires expert review and corroborating observations before any "
    "geologic claim."
)
