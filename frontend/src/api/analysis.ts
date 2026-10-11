// Analysis endpoints: reference library ("minerals") + analysis jobs (frozen contract).
//   GET  /api/minerals            -> ListResponse<SpectralReferenceSummary>
//   GET  /api/minerals/{id}       -> SpectralReference (adds wavelength[]/reflectance[])
//   POST /api/analysis-jobs       -> 202 AnalysisJob
//   GET  /api/analysis-jobs/{id}  -> AnalysisJob
//   GET  /api/analysis-jobs       -> Paginated<AnalysisJob>
import { apiFetch } from './client';
import { zSpectralReference } from './validators';
import { API_ROUTES } from '@/types';
import type {
  AnalysisJob,
  AnalysisJobCreate,
  JobListResponse,
  JobQuery,
  MineralListResponse,
  MineralQuery,
  SpectralReference,
  SpectralReferenceSummary,
} from '@/types';

export async function listMinerals(
  query: MineralQuery = {},
  signal?: AbortSignal,
): Promise<SpectralReferenceSummary[]> {
  const res = await apiFetch<MineralListResponse>(API_ROUTES.minerals, {
    query: { class: query.class, source: query.source, q: query.q },
    signal,
  });
  return res.items;
}

export async function getMineral(id: string, signal?: AbortSignal): Promise<SpectralReference> {
  return apiFetch<SpectralReference>(API_ROUTES.mineral(id), {
    signal,
    schema: zSpectralReference,
  });
}

export async function createJob(
  body: AnalysisJobCreate,
  idempotencyKey?: string,
  signal?: AbortSignal,
): Promise<AnalysisJob> {
  return apiFetch<AnalysisJob>(API_ROUTES.analysisJobs, {
    method: 'POST',
    body,
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    signal,
  });
}

export async function getJob(id: string, signal?: AbortSignal): Promise<AnalysisJob> {
  return apiFetch<AnalysisJob>(API_ROUTES.analysisJob(id), { signal });
}

export async function listJobs(
  query: JobQuery = {},
  signal?: AbortSignal,
): Promise<JobListResponse> {
  return apiFetch<JobListResponse>(API_ROUTES.analysisJobs, {
    query: {
      status: query.status,
      observation_id: query.observation_id,
      limit: query.limit,
      offset: query.offset,
    },
    signal,
  });
}
