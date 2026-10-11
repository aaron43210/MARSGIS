import type { AppSlice } from './createSlice';
import type { LayerEntry, LayerSlice } from './types';
import type { MapLayer } from '@/types';
import { listLayers } from '@/api/layers';
import { FALLBACK_BASEMAPS } from '@/config/basemaps';
import { ApiError } from '@/api/client';

function toEntry(layer: MapLayer, order: number): LayerEntry {
  return {
    id: layer.id,
    layer,
    visible: layer.default_visible,
    opacity: layer.style.opacity ?? 1,
    order,
    removable: true,
  };
}

export const createLayerSlice: AppSlice<LayerSlice> = (set, get) => ({
  baseLayers: FALLBACK_BASEMAPS,
  overlays: [],
  overlayCatalog: [],
  catalogStatus: 'idle',
  catalogError: null,

  loadLayers: async () => {
    set((state) => {
      state.catalogStatus = 'loading';
      state.catalogError = null;
    });
    try {
      const layers = await listLayers();
      const base = layers.filter((l) => l.is_base);
      const overlays = layers.filter((l) => !l.is_base);
      set((state) => {
        state.baseLayers = base.length > 0 ? base : FALLBACK_BASEMAPS;
        state.overlayCatalog = overlays;
        state.catalogStatus = 'ready';
      });
      // Ensure the selected basemap still exists; otherwise fall back to the first.
      const { basemapId, baseLayers } = get();
      if (!baseLayers.some((l) => l.id === basemapId) && baseLayers[0]) {
        get().setBasemap(baseLayers[0].id);
      }
    } catch (err) {
      // Keep a working globe with the verified fallback basemaps even when the API is down.
      const msg = err instanceof ApiError ? err.message : 'Failed to load layer catalogue.';
      set((state) => {
        state.baseLayers = FALLBACK_BASEMAPS;
        state.overlayCatalog = [];
        state.catalogStatus = 'error';
        state.catalogError = msg;
      });
    }
  },

  addOverlay: (layer) =>
    set((state) => {
      if (state.overlays.some((o) => o.id === layer.id)) return;
      state.overlays.push(toEntry(layer, state.overlays.length));
    }),

  removeOverlay: (id) =>
    set((state) => {
      state.overlays = state.overlays
        .filter((o) => o.id !== id)
        .map((o, i) => ({ ...o, order: i }));
    }),

  setLayerVisible: (id, visible) =>
    set((state) => {
      const entry = state.overlays.find((o) => o.id === id);
      if (entry) entry.visible = visible;
    }),

  setLayerOpacity: (id, opacity) =>
    set((state) => {
      const entry = state.overlays.find((o) => o.id === id);
      if (entry) entry.opacity = Math.max(0, Math.min(1, opacity));
    }),

  reorderOverlay: (id, toIndex) =>
    set((state) => {
      const from = state.overlays.findIndex((o) => o.id === id);
      if (from < 0) return;
      const clamped = Math.max(0, Math.min(state.overlays.length - 1, toIndex));
      const [moved] = state.overlays.splice(from, 1);
      if (!moved) return;
      state.overlays.splice(clamped, 0, moved);
      state.overlays.forEach((o, i) => {
        o.order = i;
      });
    }),
});
