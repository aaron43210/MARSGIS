import type { AppSlice } from './createSlice';
import type { GazetteerSlice } from './types';
import { searchGazetteer } from '@/api/gazetteer';

export const createGazetteerSlice: AppSlice<GazetteerSlice> = (set) => ({
  query: '',
  gazetteerResults: [],
  gazetteerStatus: 'idle',
  selectedFeature: null,

  // Synchronous client-side search over the bundled static IAU nomenclature list.
  // Debouncing is handled in the useGazetteer hook.
  search: (q) =>
    set((state) => {
      state.query = q;
      const results = searchGazetteer(q);
      state.gazetteerResults = results;
      state.gazetteerStatus = 'ready';
    }),

  selectFeature: (feature) =>
    set((state) => {
      state.selectedFeature = feature;
      if (feature) state.query = feature.name;
    }),
});
