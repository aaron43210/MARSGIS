import type { AppSlice } from './createSlice';
import type { CatalogSlice } from './types';
import type { BBox, ObservationQuery } from '@/types';
import { listObservations } from '@/api/catalog';
import { discoverObservations } from '@/api/discover';
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
  flyToTarget: null,
  discoverStatus: 'idle',
  lastDiscovery: null,
  discoverError: null,

  requestFlyTo: (id = null) =>
    set((state) => {
      state.flyToTarget = { id: id ?? null, timestamp: Date.now() };
    }),

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
      if (id) {
        state.flyToTarget = { id, timestamp: Date.now() };
      }
    }),

  hoverObservation: (id) =>
    set((state) => {
      state.hoveredObservationId = id;
    }),

  discover: async (bbox: BBox, label: string) => {
    set((state) => {
      state.discoverStatus = 'loading';
      state.discoverError = null;
    });
    try {
      const found = await discoverObservations(bbox, 100);
      set((state) => {
        // Merge by id (new array ref so footprints redraw); never drop existing.
        const byId = new Map(state.observations.map((o) => [o.id, o]));
        for (const o of found) byId.set(o.id, o);
        state.observations = Array.from(byId.values());
        state.total = state.observations.length;
        state.discoverStatus = 'ready';
        state.lastDiscovery = { label, found: found.length };
        // Fly to the first discovered scene (reuses the selection fly wiring).
        if (found.length > 0) {
          state.selectedObservationId = found[0]!.id;
          state.config.observation_id = found[0]!.id;
        }
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Discovery failed.';
      set((state) => {
        state.discoverStatus = 'error';
        state.discoverError = msg;
      });
    }
  },
});
