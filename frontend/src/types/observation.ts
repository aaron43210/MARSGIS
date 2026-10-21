// MarsGIS shared contract — observations & datasets.
// contract_version: 1.0.0
import type { BBox, Footprint, ISODateTime, LonLat, UrlString } from './common';
import type { DatasetKind, InstrumentType, ProductType, ServiceType } from './enums';

/** Per-detector wavelength coverage. */
export interface WavelengthRange {
  detector: string; // e.g. "VNIR" | "IR"
  min_nm: number;
  max_nm: number;
}

/** Spectral/band summary for an observation (not the full cube). */
export interface SpectralSummary {
  band_count: number;
  wavelength_min_nm: number;
  wavelength_max_nm: number;
  wavelength_unit: 'nm';
  sampling_nm: number | null;
  ranges: WavelengthRange[];
}

export interface QualityFlags {
  has_known_artifacts: boolean;
  spike_corrected: boolean;
  atmospherically_corrected: boolean;
  photometrically_corrected: boolean;
  /** 0..1 overall suitability score that drives `analysis_suitable`. */
  score: number | null;
  notes: string | null;
}

/** How a dataset's data is fetched (API/service first; no bulk archive). */
export interface DatasetAccess {
  service: ServiceType;
  url: UrlString; // base endpoint or tile/template url
  auth_required: boolean;
  notes: string | null;
}

/** A logical collection or served product that groups/sources observations. */
export interface Dataset {
  id: string;
  title: string;
  description: string | null;
  provider: string;
  kind: DatasetKind;
  instrument: InstrumentType | null;
  product_type: ProductType | null;
  spatial_extent: BBox | null;
  temporal_extent: { start: ISODateTime | null; end: ISODateTime | null } | null;
  license: string | null;
  attribution: string;
  access: DatasetAccess;
  observation_count: number | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

/** Lightweight observation for list/map rendering. */
export interface ObservationSummary {
  id: string; // native observation id, e.g. "FRT00003E12"
  instrument: InstrumentType;
  product_type: ProductType;
  title: string;
  provider: string;
  region: string | null;
  bbox: BBox;
  center: LonLat;
  footprint: Footprint;
  acquired_at: ISODateTime | null;
  resolution_m: number | null;
  analysis_suitable: boolean;
  thumbnail_url: UrlString | null;
}

/** Full observation record. */
export interface Observation extends ObservationSummary {
  target: 'Mars';
  dataset_id: string | null;
  spectral: SpectralSummary | null;
  quality: QualityFlags;
  /** Service URL used to fetch/describe the product (NOT a bulk archive link). */
  source_url: UrlString;
  browse_url: UrlString | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}
