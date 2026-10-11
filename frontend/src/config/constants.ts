// Domain constants for MarsGIS. Coordinates are Mars IAU 2000 degrees:
// longitude east-positive in [-180, 180], planetocentric latitude in [-90, 90].
// See contracts/enums.json#crs — this is NOT Earth WGS84.

import type { BBox } from '@/types';

/** Mars reference ellipsoid radii (metres). Equatorial = x = y, polar = z. */
export const MARS_RADII = {
  equatorial: 3396190,
  polar: 3376200,
} as const;

export interface RegionDef {
  id: string;
  name: string;
  /** [lon, lat] in Mars degrees (east-positive). */
  center: [number, number];
  /** [west, south, east, north] in Mars degrees. */
  bbox: BBox;
  /** Camera height (metres) for a comfortable regional view. */
  cameraHeight: number;
}

export const REGIONS: Record<string, RegionDef> = {
  nili_fossae: {
    id: 'nili_fossae',
    name: 'Nili Fossae',
    center: [77.0, 21.0],
    bbox: [74, 18, 80, 24],
    cameraHeight: 400000,
  },
};

/** Default camera on first load (global Mars view centred on the prime meridian). */
export const DEFAULT_CAMERA = {
  lon: 77.0,
  lat: 21.0,
  height: 6_000_000,
  heading: 0,
  pitch: -90, // straight down (degrees)
  roll: 0,
} as const;

/** East-positive planetocentric, [-180, 180]. Centralized in utils/format.normalizeLon. */
export const LON_CONVENTION = 'east-positive planetocentric [-180,180]';

/** uPlot/legend fallback palette (dark + light safe). */
export const SERIES_COLORS = {
  observed: '#4fc3f7',
  reference: '#ffb74d',
} as const;
