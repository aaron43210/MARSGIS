// MarsGIS shared contract — map layers, tile sources, legends (the display contract).
// contract_version: 1.0.0
import type { BBox, ISODateTime, UrlString } from './common';
import type { AvailabilityStatus, LayerType, LegendType, TileOrder, TilingScheme } from './enums';

/**
 * Tile/service source for a layer.
 * For the Mars globe, basemaps and result tiles use `tiling_scheme: "geographic"`
 * (equirectangular, 2x1 tiles at z0, north-origin rows) so overlays register exactly.
 * NASA Trek WMTS uses `tile_order: "zyx"` ({z}/{row}/{col}); our result XYZ tiles use "zxy".
 */
export interface LayerSource {
  url_template: UrlString; // e.g. ".../{z}/{y}/{x}.jpg" (Trek) or "/api/results/{id}/tiles/{z}/{x}/{y}.png"
  tiling_scheme: TilingScheme;
  tile_order: TileOrder;
  tile_size: number; // 256
  file_extension: 'jpg' | 'png';
  level_zero_tiles_x: number; // 2 for geographic Mars
  level_zero_tiles_y: number; // 1 for geographic Mars
  min_zoom: number;
  max_zoom: number;
  subdomains: string[] | null;
  tile_matrix_set: string | null; // WMTS only, e.g. "default028mm"
  request_headers: Record<string, string> | null;
  provider: string;
}

export interface LayerStyle {
  opacity: number; // 0..1
  colormap: string | null; // informational for result_tiles (baked server-side)
  value_range: [number, number] | null;
  z_index: number;
}

/** Runtime availability of a layer's source, resolved by probing a sample tile. */
export interface LayerAvailability {
  status: AvailabilityStatus;
  checked_at: ISODateTime | null;
  sample_tile_url: UrlString | null;
  http_status: number | null;
  note: string | null;
}

export interface LegendStop {
  value: number | null;
  color: string; // hex
  label: string;
}

export interface Legend {
  title: string;
  type: LegendType;
  colormap: string | null;
  value_range: [number, number] | null;
  units: string | null;
  stops: LegendStop[];
  nodata_label: string | null;
  /** Present on result legends; the candidate-not-confirmed caveat. */
  caveat: string | null;
}

/** A displayable Cesium imagery/overlay layer (catalog layer or a result layer). */
export interface MapLayer {
  id: string;
  type: LayerType;
  title: string;
  subtitle: string | null;
  is_base: boolean; // base layers are mutually exclusive; overlays stack
  default_visible: boolean;
  source: LayerSource;
  style: LayerStyle;
  attribution: string;
  availability: LayerAvailability;
  bounds: BBox | null; // null = global coverage
  legend: Legend | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}
