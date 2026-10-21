// Domain constants for MarsGIS. Coordinates are Mars IAU 2000 degrees:
// longitude east-positive in [-180, 180], planetocentric latitude in [-90, 90].
// See contracts/enums.json#crs — this is NOT Earth WGS84.

/** Default camera on first load (global Mars view centred on the prime meridian). */
export const DEFAULT_CAMERA = {
  lon: 77.0,
  lat: 21.0,
  height: 6_000_000,
  heading: 0,
  pitch: -90, // straight down (degrees)
  roll: 0,
} as const;

/** uPlot/legend fallback palette (dark + light safe). */
export const SERIES_COLORS = {
  observed: '#4fc3f7',
  reference: '#ffb74d',
} as const;
