// MarsGIS shared contract — health, query params, response envelopes, routes.
// contract_version: 1.0.0
import type { BBox, Paginated } from "./common";
import type {
  AssetRole,
  AvailabilityStatus,
  HealthStatus,
  InstrumentType,
  JobStatus,
  LayerType,
  MineralClass,
  ProductType,
} from "./enums";
import type { AnalysisJob } from "./analysis";
import type { MapLayer } from "./layer";
import type { ObservationSummary } from "./observation";
import type { SpectralReferenceSummary } from "./spectral";

export interface HealthComponent {
  status: HealthStatus;
  detail: string | null;
  latency_ms: number | null;
}
export interface HealthResponse {
  status: HealthStatus;
  version: string; // app semver
  contract_version: string; // "1.0.0"
  git_sha: string | null;
  time: string; // ISO datetime
  components: {
    db: HealthComponent;
    engine: HealthComponent;
    tiler: HealthComponent;
    queue: HealthComponent;
  };
  implemented_algorithms: string[];
}

/** Query for GET /api/observations. `bbox` serializes to "west,south,east,north". */
export interface ObservationQuery {
  instrument?: InstrumentType;
  product_type?: ProductType;
  region?: string;
  bbox?: BBox;
  suitable?: boolean; // filters analysis_suitable
  q?: string;
  limit?: number; // default 50, max 200
  offset?: number;
  sort?: "acquired_at" | "-acquired_at" | "id" | "resolution_m" | "-resolution_m";
}
export interface MineralQuery {
  class?: MineralClass;
  source?: string;
  q?: string;
}
export interface JobQuery {
  status?: JobStatus;
  observation_id?: string;
  limit?: number;
  offset?: number;
}
export interface LayerQuery {
  type?: LayerType;
  is_base?: boolean;
  availability?: AvailabilityStatus;
}

/** Envelope for small, non-paginated collections (layers, minerals). */
export interface ListResponse<T> {
  items: T[];
}
export type LayerListResponse = ListResponse<MapLayer>;
export type MineralListResponse = ListResponse<SpectralReferenceSummary>;
export type ObservationListResponse = Paginated<ObservationSummary>;
export type JobListResponse = Paginated<AnalysisJob>;

export interface ResultTilesParams {
  z: number;
  x: number;
  y: number;
  colormap?: string; // override; default per result
  rescale?: string; // "min,max" override of value_range
}
export interface ResultDownloadParams {
  asset?: AssetRole; // default "primary_metric" (cog)
}

export const API_PREFIX = "/api";
export const API_ROUTES = {
  health: "/api/health",
  layers: "/api/layers",
  observations: "/api/observations",
  observation: (id: string) => `/api/observations/${id}`,
  minerals: "/api/minerals",
  mineral: (id: string) => `/api/minerals/${id}`,
  analysisJobs: "/api/analysis-jobs",
  analysisJob: (id: string) => `/api/analysis-jobs/${id}`,
  result: (id: string) => `/api/results/${id}`,
  resultDownload: (id: string) => `/api/results/${id}/download`,
  resultTiles: (id: string) => `/api/results/${id}/tiles/{z}/{x}/{y}.png`,
  provenance: (id: string) => `/api/provenance/${id}`,
} as const;
