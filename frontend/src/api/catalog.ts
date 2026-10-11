// Observation catalogue endpoints (frozen contract).
//   GET /api/observations        -> Paginated<ObservationSummary>
//   GET /api/observations/{id}   -> Observation
import { apiFetch } from './client';
import { zObservationPage } from './validators';
import { API_ROUTES } from '@/types';
import type { Observation, ObservationListResponse, ObservationQuery } from '@/types';

function serializeBbox(bbox?: ObservationQuery['bbox']): string | undefined {
  if (!bbox) return undefined;
  return bbox.join(',');
}

export async function listObservations(
  query: ObservationQuery = {},
  signal?: AbortSignal,
): Promise<ObservationListResponse> {
  return apiFetch<ObservationListResponse>(API_ROUTES.observations, {
    query: {
      instrument: query.instrument,
      product_type: query.product_type,
      region: query.region,
      bbox: serializeBbox(query.bbox),
      suitable: query.suitable,
      q: query.q,
      limit: query.limit,
      offset: query.offset,
      sort: query.sort,
    },
    signal,
    schema: zObservationPage,
  });
}

export async function getObservation(id: string, signal?: AbortSignal): Promise<Observation> {
  return apiFetch<Observation>(API_ROUTES.observation(id), { signal });
}
