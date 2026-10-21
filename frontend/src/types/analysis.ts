// MarsGIS shared contract — analysis jobs & results.
// contract_version: 1.0.0
import type { BBox, ISODateTime } from './common';
import type { AnalysisAlgorithm, AssetRole, JobStatus } from './enums';
import type { Legend, MapLayer } from './layer';

/** SAM parameters. All optional on create (server applies defaults from contracts/enums.json). */
export interface SamParams {
  threshold_rad: number; // default 0.10; detection = angle <= threshold
  continuum_removed: boolean; // default false (SAM is albedo-invariant; continuum removal is opt-in)
  wavelength_subset_nm: [number, number] | null; // default [1000, 2600]
  bands: number[] | null; // explicit band indices; overrides subset when set
  output_resolution_m: number | null;
}
/** v1 supports SAM only; SID/BAND_RATIO params reserved. */
export type AnalysisParams = SamParams;

export interface AnalysisJobCreate {
  observation_id: string;
  algorithm: AnalysisAlgorithm; // "SAM" in v1
  reference_id: string; // SpectralReference.id (the target mineral)
  params?: Partial<SamParams>;
}

export interface JobError {
  code: string; // e.g. "OBSERVATION_FETCH_FAILED", "ENGINE_ERROR"
  message: string;
  detail: string | null;
  retriable: boolean;
}

export interface AnalysisJob {
  id: string;
  observation_id: string;
  algorithm: AnalysisAlgorithm;
  reference_id: string;
  params: AnalysisParams; // resolved (defaults applied)
  status: JobStatus;
  progress: number; // 0..1
  message: string | null;
  result_id: string | null; // set iff status === "succeeded"
  error: JobError | null; // set iff status === "failed"
  created_at: ISODateTime;
  updated_at: ISODateTime;
  started_at: ISODateTime | null;
  finished_at: ISODateTime | null;
}

export interface RasterAsset {
  href: string; // GET /api/results/{id}/download?asset=<role>
  role: AssetRole;
  media_type: string; // "image/tiff; application=geotiff; profile=cloud-optimized"
  units: string; // "radians" | "score" | "boolean"
  value_range: [number, number] | null;
  nodata: number | null;
  width: number | null;
  height: number | null;
  size_bytes: number | null;
}

export interface ResultRasters {
  cog: RasterAsset; // primary displayed metric (SAM angle)
  angle: RasterAsset; // SAM angle, radians
  mask: RasterAsset; // detection mask (angle <= threshold)
  score: RasterAsset | null; // optional match score (1 - angle/threshold)
}

export interface Histogram {
  bin_edges: number[];
  counts: number[];
}

export interface SummaryStats {
  pixel_count: number;
  valid_pixel_count: number;
  detected_pixel_count: number;
  detected_fraction: number; // 0..1
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  threshold_rad: number;
  reference_id: string;
  mineral: string;
  histogram: Histogram | null;
  caveat: string;
}

export interface AnalysisResult {
  id: string;
  job_id: string;
  observation_id: string;
  algorithm: AnalysisAlgorithm;
  reference_id: string;
  mineral: string; // snapshot label
  rasters: ResultRasters;
  bounds: BBox; // mirrors map_layer.bounds
  value_range: [number, number]; // mirrors map_layer.style.value_range
  legend: Legend; // mirrors map_layer.legend
  summary_stats: SummaryStats;
  /** Ready-to-add Cesium layer (type "result_tiles"): tiles template + scheme + bounds + legend. */
  map_layer: MapLayer;
  provenance_id: string;
  caveat: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}
