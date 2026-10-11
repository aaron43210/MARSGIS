// Live whole-Mars discovery — GET /api/observations/discover?bbox=&limit= (additive,
// not in the frozen contract). Queries PDS ODE for real CRISM MTRDR products in a
// bbox and returns them as ObservationSummary rows merged into the catalogue.
import { apiFetch } from './client';
import { env } from '@/env';
import type { BBox, ObservationSummary } from '@/types';

interface DiscoverResponse {
  items: ObservationSummary[];
  discovered: number;
  added: number;
  source: string;
}

export async function discoverObservations(
  bbox: BBox,
  limit = 100,
  signal?: AbortSignal,
): Promise<ObservationSummary[]> {
  if (env.useMocks) return []; // no live archive in offline mock mode
  const res = await apiFetch<DiscoverResponse>('/api/observations/discover', {
    query: { bbox: bbox.join(','), limit },
    signal,
  });
  return res.items;
}
