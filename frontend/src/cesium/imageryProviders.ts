// Build Cesium ImageryProviders from frozen-contract MapLayer objects.
// Basemaps + result tiles use a GeographicTilingScheme (equirectangular, 2x1 @ z0) so Trek
// basemaps and result overlays co-register with no reprojection. The Mars ellipsoid is already
// installed globally (Ellipsoid.default), so GeographicTilingScheme uses Mars radii.
import {
  GeographicTilingScheme,
  Rectangle,
  SingleTileImageryProvider,
  UrlTemplateImageryProvider,
  Credit,
  type ImageryProvider,
} from 'cesium';
import { env } from '@/env';
import type { BBox, MapLayer } from '@/types';

const TREK_ORIGIN = 'https://trek.nasa.gov';

/** Route Trek tiles through the /trek proxy when VITE_TREK_VIA_PROXY=true. */
function rewriteUrl(url: string): string {
  if (env.trekViaProxy && url.startsWith(TREK_ORIGIN)) {
    return url.replace(TREK_ORIGIN, '/trek');
  }
  return url;
}

function rectangleFromBounds(bounds: BBox | null): Rectangle {
  if (!bounds) return Rectangle.MAX_VALUE;
  const [w, s, e, n] = bounds;
  return Rectangle.fromDegrees(w, s, e, n);
}

/** True when the url_template contains tile tokens (tiled); false = single static image. */
function isTiled(layer: MapLayer): boolean {
  return /\{z\}/i.test(layer.source.url_template);
}

/** Synchronous tiled provider (used by LayerManager for basemaps/overlays/result tiles). */
export function buildTiledProvider(layer: MapLayer): UrlTemplateImageryProvider {
  const src = layer.source;
  return new UrlTemplateImageryProvider({
    url: rewriteUrl(src.url_template),
    tilingScheme: new GeographicTilingScheme({
      numberOfLevelZeroTilesX: src.level_zero_tiles_x || 2,
      numberOfLevelZeroTilesY: src.level_zero_tiles_y || 1,
    }),
    rectangle: rectangleFromBounds(layer.bounds),
    tileWidth: src.tile_size || 256,
    tileHeight: src.tile_size || 256,
    minimumLevel: src.min_zoom ?? 0,
    maximumLevel: src.max_zoom ?? 8,
    credit: new Credit(layer.attribution || src.provider || ''),
  });
}

/**
 * Build a provider for any layer: tiled -> UrlTemplate (sync, wrapped in a resolved promise);
 * single static image -> SingleTileImageryProvider.fromUrl (async). Always returns a Promise so
 * callers have one code path.
 */
export async function buildImageryProvider(layer: MapLayer): Promise<ImageryProvider> {
  if (isTiled(layer)) return buildTiledProvider(layer);
  // Tokenless url_template => a single static image stretched over the layer bounds.
  const rect = rectangleFromBounds(layer.bounds);
  return SingleTileImageryProvider.fromUrl(rewriteUrl(layer.source.url_template), {
    rectangle: rect,
    credit: new Credit(layer.attribution || layer.source.provider || ''),
  });
}
