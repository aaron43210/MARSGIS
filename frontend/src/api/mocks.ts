// Offline/CI mock backend. Active only when env.useMocks (VITE_USE_MOCKS=true).
// Serves every /api path the client calls from bundled SYNTHETIC fixtures in src/data/*.
// A submitted job advances queued -> running -> succeeded across successive polls so the
// full analysis flow works with no backend and no network.
//
// Everything served here is SYNTHETIC and is labelled as such in the payloads; it must never
// be presented as real archive data.
import observationsPage from '@/data/sample-observations.json';
import referenceSpectra from '@/data/reference-spectra.json';
import sampleResult from '@/data/sample-result.json';
import sampleResultPng from '@/data/sample-result.png';
import { FALLBACK_BASEMAPS } from '@/config/basemaps';
import { CANDIDATE_MATCH_CAVEAT } from '@/types';
import type {
  AnalysisJob,
  AnalysisResult,
  HealthResponse,
  Observation,
  ObservationSummary,
  Provenance,
  SamParams,
  SpectralReference,
  SpectralReferenceSummary,
} from '@/types';

interface MockInit {
  method?: 'GET' | 'POST';
  body?: unknown;
  query?: Record<string, unknown>;
}

const DEFAULT_PARAMS: SamParams = {
  threshold_rad: 0.1,
  continuum_removed: false,
  wavelength_subset_nm: [1000, 2600],
  bands: null,
  output_resolution_m: null,
};

const page = observationsPage as unknown as { items: ObservationSummary[]; total: number };
const refs = referenceSpectra as unknown as SpectralReference[];

function resolvedResult(): AnalysisResult {
  const r = structuredClone(sampleResult) as unknown as AnalysisResult;
  // Inject the bundled PNG asset URL as a tokenless url_template -> single-image overlay.
  r.map_layer.source.url_template = sampleResultPng;
  return r;
}

function toSummary(r: SpectralReference): SpectralReferenceSummary {
  return {
    id: r.id,
    mineral: r.mineral,
    mineral_class: r.mineral_class,
    source: r.source,
    source_id: r.source_id,
    spectrum_type: r.spectrum_type,
    resampled_to: r.resampled_to,
    point_count: r.point_count,
    wavelength_min_nm: r.wavelength_min_nm,
    wavelength_max_nm: r.wavelength_max_nm,
    diagnostic_features_nm: r.diagnostic_features_nm,
    color: r.color,
    description: r.description,
    created_at: r.created_at,
    updated_at: r.updated_at,
  };
}

function fullObservation(s: ObservationSummary): Observation {
  return {
    ...s,
    target: 'Mars',
    dataset_id: null,
    spectral: {
      band_count: 438,
      wavelength_min_nm: 1000,
      wavelength_max_nm: 2600,
      wavelength_unit: 'nm',
      sampling_nm: 6.55,
      ranges: [{ detector: 'IR', min_nm: 1000, max_nm: 2600 }],
    },
    quality: {
      has_known_artifacts: false,
      spike_corrected: true,
      atmospherically_corrected: true,
      photometrically_corrected: true,
      score: s.analysis_suitable ? 0.9 : 0.4,
      notes: 'SYNTHETIC offline fixture.',
    },
    source_url: 'https://example.invalid/synthetic',
    browse_url: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
}

interface JobRecord {
  job: AnalysisJob;
  polls: number;
}
const jobStore = new Map<string, JobRecord>();
let jobCounterSeed = 0;

function nowISO(): string {
  return new Date().toISOString();
}

function createMockJob(body: {
  observation_id: string;
  reference_id: string;
  algorithm: string;
  params?: Partial<SamParams>;
}): AnalysisJob {
  jobCounterSeed += 1;
  const id = `mock-job-${jobCounterSeed}`;
  const job: AnalysisJob = {
    id,
    observation_id: body.observation_id,
    algorithm: 'SAM',
    reference_id: body.reference_id,
    params: { ...DEFAULT_PARAMS, ...body.params },
    status: 'queued',
    progress: 0,
    message: 'Queued (offline mock).',
    result_id: null,
    error: null,
    created_at: nowISO(),
    updated_at: nowISO(),
    started_at: null,
    finished_at: null,
  };
  jobStore.set(id, { job, polls: 0 });
  return job;
}

function advanceJob(id: string): AnalysisJob | null {
  const rec = jobStore.get(id);
  if (!rec) return null;
  rec.polls += 1;
  const { job } = rec;
  if (job.status === 'succeeded' || job.status === 'failed') return job;
  if (rec.polls === 1) {
    job.status = 'running';
    job.progress = 0.4;
    job.message = 'Running SAM (offline mock).';
    job.started_at = nowISO();
  } else if (rec.polls >= 2) {
    job.status = 'succeeded';
    job.progress = 1;
    job.message = 'Completed (offline mock).';
    job.result_id = (sampleResult as unknown as AnalysisResult).id;
    job.finished_at = nowISO();
  }
  job.updated_at = nowISO();
  return job;
}

function health(): HealthResponse {
  return {
    status: 'ok',
    version: '1.0.0-mock',
    contract_version: '1.0.0',
    git_sha: null,
    time: nowISO(),
    components: {
      db: { status: 'ok', detail: 'mock fixtures', latency_ms: 0 },
      engine: { status: 'ok', detail: 'offline mock', latency_ms: 0 },
      tiler: {
        status: 'degraded',
        detail: 'single-image overlay only (offline)',
        latency_ms: null,
      },
      queue: { status: 'ok', detail: 'inprocess mock', latency_ms: 0 },
    },
    implemented_algorithms: ['SAM'],
  };
}

function provenance(): Provenance {
  const r = sampleResult as unknown as AnalysisResult;
  return {
    id: r.provenance_id,
    result_id: r.id,
    job_id: r.job_id,
    observation_id: r.observation_id,
    reference_id: r.reference_id,
    engine_image: 'ghcr.io/aaron43210/marsgis-engine:offline-mock',
    engine_version: '0.0.0-mock',
    software: [{ name: 'marsgis-engine', version: '0.0.0-mock' }],
    source_ids: [r.observation_id, r.reference_id],
    source_urls: [],
    steps: [],
    params: { threshold_rad: 0.1, continuum_removed: false },
    inputs_checksums: null,
    outputs_checksums: null,
    started_at: '2026-01-01T00:00:00Z',
    finished_at: '2026-01-01T00:00:00Z',
    timestamp: '2026-01-01T00:00:00Z',
    caveat: CANDIDATE_MATCH_CAVEAT,
  };
}

const RESULT_RE = /^\/api\/results\/([^/]+)$/;
const PROVENANCE_RE = /^\/api\/provenance\/([^/]+)$/;
const OBSERVATION_RE = /^\/api\/observations\/([^/]+)$/;
const MINERAL_RE = /^\/api\/minerals\/([^/]+)$/;
const JOB_RE = /^\/api\/analysis-jobs\/([^/]+)$/;

/** Simulated network latency so loading states are visible in the offline demo. */
function delay<T>(value: T, ms = 150): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export async function mockFetch(path: string, init: MockInit = {}): Promise<unknown> {
  const method = init.method ?? 'GET';
  const bare = path.split('?')[0] ?? path;

  if (bare === '/api/health') return delay(health());

  if (bare === '/api/layers') return delay({ items: FALLBACK_BASEMAPS });

  if (bare === '/api/observations' && method === 'GET') {
    return delay({ ...page, limit: 50, offset: 0, next_offset: null });
  }
  const obsMatch = OBSERVATION_RE.exec(bare);
  if (obsMatch) {
    const found = page.items.find((o) => o.id === obsMatch[1]);
    if (!found) throw mockNotFound('observation', obsMatch[1]!);
    return delay(fullObservation(found));
  }

  if (bare === '/api/minerals' && method === 'GET') {
    return delay({ items: refs.map(toSummary) });
  }
  const minMatch = MINERAL_RE.exec(bare);
  if (minMatch) {
    const found = refs.find((r) => r.id === minMatch[1]);
    if (!found) throw mockNotFound('mineral', minMatch[1]!);
    return delay(found);
  }

  if (bare === '/api/analysis-jobs' && method === 'POST') {
    const body = init.body as { observation_id: string; reference_id: string; algorithm: string };
    return delay(createMockJob(body), 200);
  }
  if (bare === '/api/analysis-jobs' && method === 'GET') {
    const items = [...jobStore.values()].map((r) => r.job);
    return delay({ items, total: items.length, limit: 50, offset: 0, next_offset: null });
  }
  const jobMatch = JOB_RE.exec(bare);
  if (jobMatch) {
    const job = advanceJob(jobMatch[1]!);
    if (!job) throw mockNotFound('job', jobMatch[1]!);
    return delay(job, 400);
  }

  const resMatch = RESULT_RE.exec(bare);
  if (resMatch) return delay(resolvedResult());

  if (PROVENANCE_RE.test(bare)) return delay(provenance());

  throw mockNotFound('route', bare);
}

function mockNotFound(kind: string, id: string): Error {
  const err = new Error(`Mock ${kind} not found: ${id}`);
  err.name = 'ApiError';
  return err;
}
