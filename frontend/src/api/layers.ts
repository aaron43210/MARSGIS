// Layer catalogue endpoint — GET /api/layers (frozen contract: ListResponse<MapLayer>).
import { apiFetch } from './client';
import { zLayerList } from './validators';
import { API_ROUTES } from '@/types';
import type { LayerListResponse, LayerQuery, MapLayer } from '@/types';

export async function listLayers(query?: LayerQuery, signal?: AbortSignal): Promise<MapLayer[]> {
  const res = await apiFetch<LayerListResponse>(API_ROUTES.layers, {
    query: {
      type: query?.type,
      is_base: query?.is_base,
      availability: query?.availability,
    },
    signal,
    schema: zLayerList,
  });
  return res.items;
}
