// Coordinate / number formatting for the Mars (east-positive, planetocentric) convention.
import { normalizeLon180, normalizeLon360 } from '@/cesium/geo';

export { normalizeLon180, normalizeLon360 };

/** Format a longitude with E/W hemisphere suffix (east-positive input, [-180,180]). */
export function formatLon(lon: number, digits = 2): string {
  const n = normalizeLon180(lon);
  const hemi = n >= 0 ? 'E' : 'W';
  return `${Math.abs(n).toFixed(digits)}°${hemi}`;
}

/** Format a planetocentric latitude with N/S hemisphere suffix. */
export function formatLat(lat: number, digits = 2): string {
  const hemi = lat >= 0 ? 'N' : 'S';
  return `${Math.abs(lat).toFixed(digits)}°${hemi}`;
}

export function formatLonLat(lon: number, lat: number, digits = 2): string {
  return `${formatLat(lat, digits)}, ${formatLon(lon, digits)}`;
}

/** Metres -> a compact km/m string. */
export function formatKm(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(meters >= 100000 ? 0 : 1)} km`;
  return `${Math.round(meters)} m`;
}

export function radToDeg(rad: number): number {
  return (rad * 180) / Math.PI;
}

export function degToRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/** Format a spectral angle given in radians as "0.057 rad (3.27°)". */
export function formatAngle(rad: number, digits = 3): string {
  return `${rad.toFixed(digits)} rad (${radToDeg(rad).toFixed(2)}°)`;
}

export function formatDeg(deg: number, digits = 2): string {
  return `${deg.toFixed(digits)}°`;
}

export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatInt(n: number): string {
  return n.toLocaleString('en-US');
}
