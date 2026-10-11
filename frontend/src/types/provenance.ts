// MarsGIS shared contract — provenance (reproducibility record for a result).
// contract_version: 1.0.0
import type { ISODateTime } from "./common";
import type { ProvenanceStepStatus } from "./enums";

export interface SoftwareComponent {
  name: string; // "marsgis-engine" | "rasterio" | "spectral" | "numpy" | "GDAL" ...
  version: string;
}

export interface ProvenanceStep {
  order: number;
  name: string; // "fetch_observation" | "read_bands" | "continuum_removal" | "resample_reference" | "sam" | "threshold" | "write_cog" | "compute_stats"
  software: string;
  version: string | null;
  params: Record<string, unknown> | null;
  started_at: ISODateTime;
  finished_at: ISODateTime;
  status: ProvenanceStepStatus;
  message: string | null;
}

export interface Provenance {
  id: string;
  result_id: string;
  job_id: string;
  observation_id: string;
  reference_id: string;
  engine_image: string; // "ghcr.io/<account>/marsgis-engine:<tag>"
  engine_version: string; // semver or git sha
  software: SoftwareComponent[];
  source_ids: string[]; // [observation_id, reference_id, dataset ids]
  source_urls: string[]; // service URLs actually fetched
  steps: ProvenanceStep[]; // ordered pipeline steps
  params: Record<string, unknown>; // resolved params echoed
  inputs_checksums: Record<string, string> | null; // {asset: sha256}
  outputs_checksums: Record<string, string> | null;
  started_at: ISODateTime;
  finished_at: ISODateTime;
  timestamp: ISODateTime; // when this record was written
  caveat: string;
}
