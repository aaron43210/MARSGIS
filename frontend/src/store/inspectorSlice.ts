import type { AppSlice } from './createSlice';
import type { InspectorSlice } from './types';
import type { AnalysisResult } from '@/types';
import { getMineral } from '@/api/analysis';
import { getResult, getResultPixel } from '@/api/results';
import { ApiError } from '@/api/client';

/**
 * Pixel inspector. A click loads the REAL spectrum and SAM angle of the pixel under the
 * cursor from GET /api/results/{id}/pixel — computed from the same image and bands SAM used.
 * Nothing is generated client-side: a different pixel returns a different spectrum.
 */
export const createInspectorSlice: AppSlice<InspectorSlice> = (set, get) => ({
  open: false,
  inspectorStatus: 'idle',
  inspectorError: null,
  point: null,
  referenceId: null,
  reference: null,
  pixel: null,

  inspectPixel: async (resultId, lon, lat) => {
    set((state) => {
      state.open = true;
      state.inspectorStatus = 'loading';
      state.inspectorError = null;
      state.point = { lon, lat };
      state.pixel = null;
      // Surface the inspector panel on the right dock.
      state.panels.right.active = 'inspector';
      state.panels.right.open = true;
    });
    try {
      let result: AnalysisResult | undefined = get().results[resultId];
      result ??= await getResult(resultId);
      const [reference, pixel] = await Promise.all([
        getMineral(result.reference_id),
        getResultPixel(resultId, lon, lat),
      ]);
      // Ignore a stale response if the user clicked another pixel meanwhile.
      const p = get().point;
      if (!p || p.lon !== lon || p.lat !== lat) return;
      set((state) => {
        state.referenceId = reference.id;
        state.reference = reference;
        state.pixel = pixel;
        state.inspectorStatus = 'ready';
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load the pixel spectrum.';
      set((state) => {
        state.inspectorStatus = 'error';
        state.inspectorError = msg;
      });
    }
  },

  clearInspector: () =>
    set((state) => {
      state.open = false;
      state.inspectorStatus = 'idle';
      state.inspectorError = null;
      state.point = null;
      state.reference = null;
      state.pixel = null;
    }),
});
