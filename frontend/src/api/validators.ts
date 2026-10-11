// zod validators for the few network payloads the Cesium render path depends on.
// Pattern: validate structure, then return the ORIGINAL object typed as the frozen contract
// type (so we never silently drop contract fields we don't explicitly validate).
//
// zod's default object behaviour strips unknown keys (it does not reject them), so these schemas
// stay tolerant of additive backend changes while still catching missing/malformed critical fields.
import { z } from 'zod';
import type { Footprint } from '@/types';

export function validate<T>(schema: z.ZodType, data: unknown): T {
  schema.parse(data);
  return data as T;
}

const zNumberArray = z.array(z.number());
const zBBox = z.tuple([z.number(), z.number(), z.number(), z.number()]);

const zLayerSource = z.object({
  url_template: z.string().min(1),
  tiling_scheme: z.string(),
  tile_order: z.string(),
  tile_size: z.number(),
  file_extension: z.string(),
  level_zero_tiles_x: z.number(),
  level_zero_tiles_y: z.number(),
  min_zoom: z.number(),
  max_zoom: z.number(),
});

export const zMapLayer = z.object({
  id: z.string().min(1),
  type: z.string(),
  title: z.string(),
  is_base: z.boolean(),
  default_visible: z.boolean(),
  source: zLayerSource,
  style: z.object({ opacity: z.number(), z_index: z.number() }),
  bounds: zBBox.nullable(),
});

export const zLayerList = z.object({ items: z.array(zMapLayer) });

const zPosition = z.array(z.number());
const zRing = z.array(zPosition);
const zPolygon = z.object({ type: z.literal('Polygon'), coordinates: z.array(zRing) });
const zMultiPolygon = z.object({
  type: z.literal('MultiPolygon'),
  coordinates: z.array(z.array(zRing)),
});
export const zFootprint = z.union([zPolygon, zMultiPolygon]);

export const zObservationSummary = z.object({
  id: z.string().min(1),
  instrument: z.string(),
  product_type: z.string(),
  title: z.string(),
  bbox: zBBox,
  center: z.object({ lon: z.number(), lat: z.number() }),
  footprint: zFootprint,
  analysis_suitable: z.boolean(),
});

export const zObservationPage = z.object({
  items: z.array(zObservationSummary),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
  next_offset: z.number().nullable(),
});

export const zAnalysisResult = z.object({
  id: z.string().min(1),
  observation_id: z.string(),
  reference_id: z.string(),
  mineral: z.string(),
  bounds: zBBox,
  value_range: z.tuple([z.number(), z.number()]),
  map_layer: zMapLayer,
  summary_stats: z.object({ caveat: z.string().min(1) }),
  legend: z.object({ caveat: z.string().nullable() }),
  caveat: z.string().min(1),
});

export const zSpectralReference = z
  .object({
    id: z.string().min(1),
    mineral: z.string(),
    wavelength: zNumberArray,
    reflectance: zNumberArray,
  })
  .refine((v) => v.wavelength.length === v.reflectance.length, {
    message: 'wavelength[] and reflectance[] must be equal length',
  });

/** GeoJSON footprint validator used when drawing clickable polygons. */
export function validateFootprint(d: unknown): Footprint {
  return validate<Footprint>(zFootprint, d);
}
