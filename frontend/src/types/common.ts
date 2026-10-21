// MarsGIS shared contract — common primitive & envelope types.
// contract_version: 1.0.0

/** RFC 3339 / ISO 8601 UTC timestamp, e.g. "2026-10-11T00:00:00Z". */
export type ISODateTime = string;
export type UrlString = string;

/**
 * Axis-aligned bounds as [west, south, east, north] in Mars IAU 2000 degrees.
 * Longitude east-positive in [-180, 180]; latitude planetocentric in [-90, 90].
 * This is NOT Earth WGS84 — see contracts/enums.json#crs.
 */
export type BBox = [west: number, south: number, east: number, north: number];

export interface LonLat {
  lon: number;
  lat: number;
}

/** GeoJSON geometry; coordinates are Mars degrees [lon, lat] (optionally with elevation). */
export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}
export interface GeoJSONMultiPolygon {
  type: 'MultiPolygon';
  coordinates: number[][][][];
}
export type Footprint = GeoJSONPolygon | GeoJSONMultiPolygon;

/** Uniform list envelope for every collection endpoint. */
export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  /** offset to pass for the next page, or null when exhausted. */
  next_offset: number | null;
}

export interface FieldError {
  field: string;
  message: string;
}

/** Uniform error body for every non-2xx response (also used for 422 validation). */
export interface ErrorResponse {
  code: string;
  message: string;
  detail?: string | null;
  request_id?: string | null;
  errors?: FieldError[] | null;
}
