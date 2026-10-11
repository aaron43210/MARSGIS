// MarsGIS shared contract — canonical enumerations.
// MIRROR of contracts/enums.json. Do not edit one without the other.
// contract_version: 1.0.0

export const INSTRUMENT_TYPES = ["CRISM", "CTX", "HiRISE", "HRSC", "OMEGA", "THEMIS", "MOLA"] as const;
export type InstrumentType = (typeof INSTRUMENT_TYPES)[number];

export const PRODUCT_TYPES = ["MTRDR", "TRDR", "DDR", "MOSAIC", "DEM", "ORTHOIMAGE", "BASEMAP"] as const;
export type ProductType = (typeof PRODUCT_TYPES)[number];

export const ANALYSIS_ALGORITHMS = ["SAM", "SID", "BAND_RATIO"] as const;
export type AnalysisAlgorithm = (typeof ANALYSIS_ALGORITHMS)[number];
/** Algorithms whose engine implementation is guaranteed in v1. Others validate-reject with 422. */
export const IMPLEMENTED_ALGORITHMS_V1: AnalysisAlgorithm[] = ["SAM"];

export const JOB_STATUSES = ["queued", "running", "succeeded", "failed"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];
/** Allowed job state transitions. Terminal states have no outgoing edges. */
export const JOB_STATUS_TRANSITIONS: Record<JobStatus, JobStatus[]> = {
  queued: ["running", "failed"],
  running: ["succeeded", "failed"],
  succeeded: [],
  failed: [],
};
export const TERMINAL_JOB_STATUSES: JobStatus[] = ["succeeded", "failed"];

export const LAYER_TYPES = ["basemap", "wmts", "xyz", "result_tiles", "geojson_overlay"] as const;
export type LayerType = (typeof LAYER_TYPES)[number];

export const TILING_SCHEMES = ["geographic", "mercator"] as const;
export type TilingScheme = (typeof TILING_SCHEMES)[number];

export const TILE_ORDERS = ["zyx", "zxy"] as const;
export type TileOrder = (typeof TILE_ORDERS)[number];

export const MINERAL_CLASSES = ["carbonate", "olivine", "phyllosilicate", "pyroxene", "sulfate", "iron_oxide", "hydrated_silica", "other"] as const;
export type MineralClass = (typeof MINERAL_CLASSES)[number];

export const AVAILABILITY_STATUSES = ["verified", "unconfirmed", "unavailable"] as const;
export type AvailabilityStatus = (typeof AVAILABILITY_STATUSES)[number];

export const ASSET_ROLES = ["primary_metric", "sam_angle", "detection_mask", "match_score"] as const;
export type AssetRole = (typeof ASSET_ROLES)[number];

export const LEGEND_TYPES = ["continuous", "categorical"] as const;
export type LegendType = (typeof LEGEND_TYPES)[number];

export const SPECTRUM_TYPES = ["reflectance", "continuum_removed"] as const;
export type SpectrumType = (typeof SPECTRUM_TYPES)[number];

export const HEALTH_STATUSES = ["ok", "degraded", "down"] as const;
export type HealthStatus = (typeof HEALTH_STATUSES)[number];

export const PROVENANCE_STEP_STATUSES = ["succeeded", "failed"] as const;
export type ProvenanceStepStatus = (typeof PROVENANCE_STEP_STATUSES)[number];

export const DATASET_KINDS = ["observation_collection", "mosaic", "dem", "basemap", "reference_library"] as const;
export type DatasetKind = (typeof DATASET_KINDS)[number];

export const SERVICE_TYPES = ["WMTS", "WMS", "XYZ", "REST", "STAC", "LOCAL"] as const;
export type ServiceType = (typeof SERVICE_TYPES)[number];

/** Candidate-not-confirmed caveat. MUST accompany every rendered detection result. */
export const CANDIDATE_MATCH_CAVEAT =
  "Candidate spectral match (SAM angle below threshold). NOT a confirmed mineral deposit; requires expert review and corroborating observations before any geologic claim.";
