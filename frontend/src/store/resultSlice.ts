import type { AppSlice } from './createSlice';
import type { ResultSlice } from './types';
import { getResult } from '@/api/results';
import { ApiError } from '@/api/client';

export const createResultSlice: AppSlice<ResultSlice> = (set) => ({
  results: {},
  activeResultId: null,
  overlayVisible: true,
  overlayOpacity: 0.8,
  loadStatus: 'idle',
  loadError: null,

  loadResult: async (id) => {
    set((state) => {
      state.loadStatus = 'loading';
      state.loadError = null;
    });
    try {
      const result = await getResult(id);
      set((state) => {
        state.results[result.id] = result;
        state.activeResultId = result.id;
        state.overlayVisible = true;
        state.overlayOpacity = result.map_layer.style.opacity ?? 0.8;
        state.loadStatus = 'ready';
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load result.';
      set((state) => {
        state.loadStatus = 'error';
        state.loadError = msg;
      });
    }
  },

  setActiveResult: (id) =>
    set((state) => {
      state.activeResultId = id;
    }),

  setOverlayVisible: (visible) =>
    set((state) => {
      state.overlayVisible = visible;
    }),

  setOverlayOpacity: (opacity) =>
    set((state) => {
      state.overlayOpacity = Math.max(0, Math.min(1, opacity));
    }),
});
