// The four VERIFIED NASA Trek basemaps as frozen-contract MapLayer objects.
// These are a FRONTEND FALLBACK only (offline/mocks, or if GET /api/layers fails);
// the authoritative layer catalogue comes from the backend. Product IDs below are the
// only ones re-confirmed HTTP 200 this session (see docs/.../_GLOBAL.md). Everything else
// must be discovered by the backend via Trek capabilities, never guessed here.

import type { MapLayer } from '@/types';

/** Trek EQ WMTS template. The literal double slash is REQUIRED (verified 200). */
export const TREK_TEMPLATE =
  'https://trek.nasa.gov/tiles/Mars/EQ/{product}/1.0.0//default/default028mm/{z}/{y}/{x}.{ext}';

interface TrekProduct {
  id: string;
  title: string;
  subtitle: string;
  product: string;
  ext: 'jpg' | 'png';
  maxZoom: number;
}

const TREK_PRODUCTS: TrekProduct[] = [
  {
    id: 'viking',
    title: 'Viking Color Mosaic',
    subtitle: 'MDIM 2.1 · 232 m/px',
    product: 'Viking_MDIM21_ClrMosaic_232m',
    ext: 'jpg',
    maxZoom: 7,
  },
  {
    id: 'mola_clrshade',
    title: 'MOLA Color Shaded Relief',
    subtitle: 'MGS MOLA · 463 m/px',
    product: 'MGS_MOLA_ClrShade_merge_463m',
    ext: 'jpg',
    maxZoom: 6,
  },
  {
    id: 'mola_dem',
    title: 'MOLA Elevation (DEM)',
    subtitle: 'MOLA128/64 merge',
    product: 'mola128_mola64_merge_90Nto90S_SimpleC_clon0',
    ext: 'png',
    maxZoom: 6,
  },
  {
    id: 'themis_dayir',
    title: 'THEMIS Day IR',
    subtitle: 'Controlled Mosaic · 100 m/px',
    product: 'THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018',
    ext: 'png',
    maxZoom: 7,
  },
];

const NOW = '2026-01-01T00:00:00Z';

function trekBasemap(p: TrekProduct, index: number): MapLayer {
  const url = TREK_TEMPLATE.replace('{product}', p.product).replace('{ext}', p.ext);
  return {
    id: p.id,
    type: 'basemap',
    title: p.title,
    subtitle: p.subtitle,
    is_base: true,
    default_visible: index === 0,
    source: {
      url_template: url,
      tiling_scheme: 'geographic',
      tile_order: 'zyx',
      tile_size: 256,
      file_extension: p.ext,
      level_zero_tiles_x: 2,
      level_zero_tiles_y: 1,
      min_zoom: 0,
      max_zoom: p.maxZoom,
      subdomains: null,
      tile_matrix_set: 'default028mm',
      request_headers: null,
      provider: 'NASA Mars Trek',
    },
    style: { opacity: 1, colormap: null, value_range: null, z_index: 0 },
    attribution: 'NASA/JPL-Caltech/USGS — Mars Trek',
    availability: {
      status: 'verified',
      checked_at: NOW,
      sample_tile_url: url.replace('{z}', '0').replace('{y}', '0').replace('{x}', '0'),
      http_status: 200,
      note: 'Re-verified HTTP 200 this session.',
    },
    bounds: null,
    legend: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

/** The four verified basemaps as MapLayer[] (frontend offline fallback). */
export const FALLBACK_BASEMAPS: MapLayer[] = TREK_PRODUCTS.map(trekBasemap);

export const DEFAULT_BASEMAP_ID = FALLBACK_BASEMAPS[0]!.id;
