import type { AppSlice } from './createSlice';
import type { AnalysisSlice } from './types';
import type { AnalysisJobCreate, SpectralReferenceSummary } from '@/types';
import { createJob, listMinerals } from '@/api/analysis';
import { ApiError } from '@/api/client';

/** Carbonate first (the headline Nili Fossae mineral), then alphabetical by label. */
function sortMinerals(items: SpectralReferenceSummary[]): SpectralReferenceSummary[] {
  return [...items].sort((a, b) => {
    const ca = a.mineral_class === 'carbonate' ? 0 : 1;
    const cb = b.mineral_class === 'carbonate' ? 0 : 1;
    return ca - cb || a.mineral.localeCompare(b.mineral);
  });
}

export const createAnalysisSlice: AppSlice<AnalysisSlice> = (set, get) => ({
  minerals: [],
  mineralsStatus: 'idle',
  mineralsError: null,
  config: { observation_id: null, algorithm: 'SAM', reference_id: null, params: {} },
  jobs: {},
  activeJobId: null,
  submitStatus: 'idle',
  submitError: null,

  loadMinerals: async () => {
    set((state) => {
      state.mineralsStatus = 'loading';
      state.mineralsError = null;
    });
    try {
      const items = await listMinerals();
      set((state) => {
        state.minerals = sortMinerals(items);
        state.mineralsStatus = 'ready';
        // Default the reference to the first carbonate if none chosen yet.
        if (!state.config.reference_id && state.minerals[0]) {
          state.config.reference_id = state.minerals[0].id;
        }
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load reference library.';
      set((state) => {
        state.minerals = [];
        state.mineralsStatus = 'error';
        state.mineralsError = msg;
      });
    }
  },

  setReference: (referenceId) =>
    set((state) => {
      state.config.reference_id = referenceId;
    }),

  setThresholdRad: (thresholdRad) =>
    set((state) => {
      state.config.params.threshold_rad = Math.max(0.001, Math.min(1.5, thresholdRad));
    }),

  submitJob: async () => {
    const { config } = get();
    if (!config.observation_id || !config.reference_id) {
      set((state) => {
        state.submitStatus = 'error';
        state.submitError = 'Select an observation and a reference spectrum first.';
      });
      return;
    }
    set((state) => {
      state.submitStatus = 'loading';
      state.submitError = null;
    });
    const body: AnalysisJobCreate = {
      observation_id: config.observation_id,
      algorithm: 'SAM',
      reference_id: config.reference_id,
      params: config.params,
    };
    try {
      const job = await createJob(body);
      set((state) => {
        state.jobs[job.id] = job;
        state.activeJobId = job.id;
        state.submitStatus = 'ready';
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to submit analysis job.';
      set((state) => {
        state.submitStatus = 'error';
        state.submitError = msg;
      });
    }
  },

  updateJob: (job) => {
    set((state) => {
      state.jobs[job.id] = job;
    });
    // On completion, load the result and move the user to the Results workspace.
    if (job.status === 'succeeded' && job.result_id) {
      void get().loadResult(job.result_id);
      get().setMode('results');
    }
  },

  setActiveJob: (id) =>
    set((state) => {
      state.activeJobId = id;
    }),
});
