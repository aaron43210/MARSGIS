import type { AppSlice } from './createSlice';
import type { CatalogSlice } from './types';
import type { ObservationQuery } from '@/types';
import { listObservations } from '@/api/catalog';
import { ApiError } from '@/api/client';

const INITIAL_FILTERS: ObservationQuery = {
  instrument: 'CRISM',
  product_type: 'MTRDR',
  region: 'Nili Fossae',
  limit: 50,
};

export const createCatalogSlice: AppSlice<CatalogSlice> = (set, get) => ({
  observations: [],
  total: 0,
  filters: INITIAL_FILTERS,
  observationsStatus: 'idle',
  observationsError: null,
  selectedObservationId: null,
  hoveredObservationId: null,

  loadObservations: async () => {
    set((state) => {
      state.observationsStatus = 'loading';
      state.observationsError = null;
    });
    try {
      const page = await listObservations(get().filters);
      set((state) => {
        state.observations = page.items;
        state.total = page.total;
        state.observationsStatus = 'ready';
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load observations.';
      set((state) => {
        state.observations = [];
        state.total = 0;
        state.observationsStatus = 'error';
        state.observationsError = msg;
      });
    }
  },

  setFilters: (patch) =>
    set((state) => {
      state.filters = { ...state.filters, ...patch };
    }),

  selectObservation: (id) =>
    set((state) => {
      state.selectedObservationId = id;
      // Auto-populate the analysis config so switching to Analysis mode is one click.
      state.config.observation_id = id;
    }),

  hoverObservation: (id) =>
    set((state) => {
      state.hoveredObservationId = id;
    }),
});
