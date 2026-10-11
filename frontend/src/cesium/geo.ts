// Pure geometry/GeoJSON helpers for Mars degrees. No Cesium import -> unit-testable in jsdom.
import type { BBox, Footprint } from '@/types';

/** Normalize a longitude to [-180, 180] (east-positive). */
export function normalizeLon180(lon: number): number {
  let x = ((lon + 180) % 360 + 360) % 360 - 180;
  // Keep +180 as +180 rather than -180 for a clean east edge.
  if (x === -180) x = 180;
  return x;
}

/** Normalize a longitude to [0, 360). */
export function normalizeLon360(lon: number): number {
  return ((lon % 360) + 360) % 360;
}

/** Normalize with an explicit target range. */
export function normalizeLon(lon: number, to: '180' | '360' = '180'): number {
  return to === '360' ? normalizeLon360(lon) : normalizeLon180(lon);
}

export function clampLat(lat: number): number {
  return Math.max(-90, Math.min(90, lat));
}

/** Flatten all [lon,lat] vertices of a Polygon/MultiPolygon footprint. */
function footprintPositions(f: Footprint): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  const rings: number[][][] =
    f.type === 'Polygon' ? f.coordinates : f.coordinates.flat();
  for (const ring of rings) {
    for (const pt of ring) {
      if (pt.length >= 2) out.push([pt[0]!, pt[1]!]);
    }
  }
  return out;
}

/**
 * Axis-aligned bbox [w, s, e, n] of a footprint.
 * NOTE: antimeridian-naive — a footprint crossing +/-180 will produce a bbox spanning the
 * full longitude range. CRISM MTRDR footprints near Nili Fossae never cross it.
 */
export function bboxOfFeature(f: Footprint): BBox {
  const pts = footprintPositions(f);
  if (pts.length === 0) return [-180, -90, 180, 90];
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const [lon, lat] of pts) {
    if (lon < w) w = lon;
    if (lon > e) e = lon;
    if (lat < s) s = lat;
    if (lat > n) n = lat;
  }
  return [w, s, e, n];
}

/** Centroid [lon, lat] of a footprint (arithmetic mean of vertices; antimeridian-naive). */
export function centroidOfFeature(f: Footprint): [number, number] {
  const pts = footprintPositions(f);
  if (pts.length === 0) return [0, 0];
  let sx = 0;
  let sy = 0;
  for (const [lon, lat] of pts) {
    sx += lon;
    sy += lat;
  }
  return [sx / pts.length, sy / pts.length];
}

/** Center [lon,lat] of a bbox. */
export function centerOfBbox(bbox: BBox): [number, number] {
  return [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2];
}

/** Rough camera height (m) to frame a bbox span, clamped to sane Mars-scale bounds. */
export function cameraHeightForBbox(bbox: BBox): number {
  const spanDeg = Math.max(bbox[2] - bbox[0], bbox[3] - bbox[1], 0.1);
  // ~59.3 km per degree on Mars; frame with ~3x padding.
  const meters = spanDeg * 59300 * 3;
  return Math.max(50_000, Math.min(8_000_000, meters));
}
