// MarsGIS shared contract — spectral reference library ("minerals").
// contract_version: 1.0.0
import type { ISODateTime } from "./common";
import type { MineralClass, SpectrumType } from "./enums";

/** Lightweight reference entry (no sample arrays) for GET /api/minerals. */
export interface SpectralReferenceSummary {
  id: string; // slug, e.g. "mica_carbonate_calcite"
  mineral: string; // display label, e.g. "Calcite (carbonate)"
  mineral_class: MineralClass;
  source: string; // "CRISM MICA" | "USGS splib07" | "RELAB" ...
  source_id: string | null;
  spectrum_type: SpectrumType;
  resampled_to: string | null; // instrument band set these are resampled to, e.g. "CRISM_MTRDR"
  point_count: number;
  wavelength_min_nm: number;
  wavelength_max_nm: number;
  diagnostic_features_nm: number[] | null; // key absorption band centers
  color: string; // hex, suggested plot/legend color
  description: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

/** Full reference spectrum (with sample arrays) for GET /api/minerals/{id}. */
export interface SpectralReference extends SpectralReferenceSummary {
  wavelength_unit: "nm";
  /** Ascending; same length as `reflectance`. */
  wavelength: number[];
  /** Unitless reflectance (or continuum-removed) aligned to `wavelength`. */
  reflectance: number[];
}
