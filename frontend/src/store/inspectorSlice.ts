import type { AppSlice } from './createSlice';
import type { InspectorSlice, ObservedSpectrum } from './types';
import type { AnalysisResult, SpectralReference } from '@/types';
import { getMineral } from '@/api/analysis';
import { getResult } from '@/api/results';
import { env } from '@/env';
import { ApiError } from '@/api/client';

/**
 * SYNTHETIC observed-pixel spectrum for OFFLINE/mock mode only.
 *
 * The frozen API (contracts/openapi.yaml) exposes NO per-pixel spectrum endpoint, so a real
 * observed trace cannot be fetched in v1. In mock mode we derive a clearly-labelled synthetic
 * trace from the reference so the inspector plot is demonstrable; `synthetic` is always true and
 * MUST be surfaced in the UI. It is never presented as real archive data.
 */
function syntheticObserved(reference: SpectralReference, thresholdRad: number): ObservedSpectrum {
  const reflectance = reference.reflectance.map((v, i) => {
    const wobble = 0.03 * Math.sin(i * 0.9);
    return Math.max(0, Math.min(1, v * 0.96 + wobble));
  });
  return {
    wavelength_nm: reference.wavelength,
    reflectance,
    synthetic: true,
    angle_deg: (thresholdRad * 0.6 * 180) / Math.PI,
  };
}

export const createInspectorSlice: AppSlice<InspectorSlice> = (set, get) => ({
  open: false,
  inspectorStatus: 'idle',
  inspectorError: null,
  point: null,
  referenceId: null,
  reference: null,
  observed: null,

  inspectPixel: async (resultId, lon, lat) => {
    set((state) => {
      state.open = true;
      state.inspectorStatus = 'loading';
      state.inspectorError = null;
      state.point = { lon, lat };
      state.observed = null;
      // Surface the inspector panel on the right dock.
      state.panels.right.active = 'inspector';
      state.panels.right.open = true;
    });
    try {
      let result: AnalysisResult | undefined = get().results[resultId];
      result ??= await getResult(resultId);
      const reference = await getMineral(result.reference_id);
      const observed = env.useMocks
        ? syntheticObserved(reference, result.summary_stats.threshold_rad)
        : null;
      set((state) => {
        state.referenceId = reference.id;
        state.reference = reference;
        state.observed = observed;
        state.inspectorStatus = 'ready';
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load spectrum.';
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
      state.observed = null;
    }),
});
