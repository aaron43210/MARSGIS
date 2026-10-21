// NASA Mars Trek WMTS basemap presets + Cesium imagery provider factory.
// All basemaps are the global equirectangular (2x1 @ z0) Trek grid, so they
// co-register on a GeographicTilingScheme with the Mars ellipsoid.
import { Credit, GeographicTilingScheme, UrlTemplateImageryProvider } from 'cesium';

export type BasemapId = 'viking' | 'mola' | 'mola-dem' | 'themis';

export interface BasemapDef {
  id: BasemapId;
  title: string;
  /** Trek product identifier. */
  product: string;
  /** Tile file extension (verified per product). */
  ext: 'jpg' | 'png';
  maxZoom: number;
  attribution: string;
}

const TREK = 'https://trek.nasa.gov/tiles/Mars/EQ';
const ATTR = 'NASA/JPL/USGS — Mars Trek (WMTS)';

/** Verified-reachable Trek products (HTTP 200 global tiles). */
export const BASEMAPS: Record<BasemapId, BasemapDef> = {
  viking: {
    id: 'viking',
    title: 'Viking MDIM 2.1 Color Mosaic (232 m)',
    product: 'Mars_Viking_MDIM21_ClrMosaic_global_232m',
    ext: 'jpg',
    maxZoom: 7,
    attribution: ATTR,
  },
  mola: {
    id: 'mola',
    title: 'MOLA Color Shaded Relief (463 m)',
    product: 'Mars_MGS_MOLA_ClrShade_merge_global_463m',
    ext: 'jpg',
    maxZoom: 6,
    attribution: ATTR,
  },
  'mola-dem': {
    id: 'mola-dem',
    title: 'MOLA Elevation (grayscale, 463 m)',
    product: 'mola128_mola64_merge_90Nto90S_SimpleC_clon0',
    ext: 'png',
    maxZoom: 6,
    attribution: `${ATTR} — visual DEM render, not metric elevation`,
  },
  themis: {
    id: 'themis',
    title: 'THEMIS Day IR (100 m)',
    product: 'THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018',
    ext: 'png',
    maxZoom: 7,
    attribution: ATTR,
  },
};

function getBasemap(id: BasemapId): BasemapDef {
  const b = Object.prototype.hasOwnProperty.call(BASEMAPS, id) ? BASEMAPS[id] : undefined;
  if (!b) {
    throw new Error(
      `[mars-globe] Unknown basemap "${String(id)}". Expected one of: ${Object.keys(BASEMAPS).join(', ')}.`,
    );
  }
  return b;
}

/** The URL template for one basemap ({z}/{y}/{x} = TileMatrix/Row/Col). */
export function basemapUrl(id: BasemapId): string {
  const b = getBasemap(id);
  return `${TREK}/${b.product}/1.0.0//default/default028mm/{z}/{y}/{x}.${b.ext}`;
}

/** Build a Cesium ImageryProvider for a Mars Trek basemap on the geographic grid. */
export function basemapProvider(id: BasemapId): UrlTemplateImageryProvider {
  const b = getBasemap(id);
  return new UrlTemplateImageryProvider({
    url: basemapUrl(id),
    tilingScheme: new GeographicTilingScheme({
      numberOfLevelZeroTilesX: 2,
      numberOfLevelZeroTilesY: 1,
    }),
    minimumLevel: 0,
    maximumLevel: b.maxZoom,
    credit: new Credit(b.attribution),
  });
}
