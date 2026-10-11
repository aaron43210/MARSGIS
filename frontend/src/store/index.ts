import { create } from 'zustand';
import { persist, createJSONStorage, type StateStorage } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import type { AppState } from './types';
import { createViewSlice } from './viewSlice';
import { createLayerSlice } from './layerSlice';
import { createCatalogSlice } from './catalogSlice';
import { createAnalysisSlice } from './analysisSlice';
import { createResultSlice } from './resultSlice';
import { createInspectorSlice } from './inspectorSlice';
import { createGazetteerSlice } from './gazetteerSlice';

/**
 * A StateStorage backed by window.localStorage that never throws. If localStorage is
 * missing (SSR, unit tests) or any access throws (private mode, disabled cookies, quota),
 * it transparently falls back to an in-memory store so persistence degrades silently
 * instead of crashing the app (project rule: browser storage must never crash the app).
 */
function createSafeStorage(): StateStorage {
  const memory = new Map<string, string>();
  let backing: Storage | null | undefined; // undefined = not yet resolved

  const local = (): Storage | null => {
    if (backing !== undefined) return backing;
    try {
      backing = typeof localStorage !== 'undefined' ? localStorage : null;
    } catch {
      // Accessing the global itself can throw (e.g. storage disabled by policy).
      backing = null;
    }
    return backing;
  };

  return {
    getItem: (name) => {
      const ls = local();
      if (ls) {
        try {
          return ls.getItem(name);
        } catch {
          // fall through to the in-memory copy
        }
      }
      return memory.get(name) ?? null;
    },
    setItem: (name, value) => {
      memory.set(name, value);
      const ls = local();
      if (ls) {
        try {
          ls.setItem(name, value);
        } catch {
          // keep the in-memory copy; persistence is best-effort
        }
      }
    },
    removeItem: (name) => {
      memory.delete(name);
      const ls = local();
      if (ls) {
        try {
          ls.removeItem(name);
        } catch {
          // nothing more to do
        }
      }
    },
  };
}

export const useStore = create<AppState>()(
  persist(
    immer((...a) => ({
      ...createViewSlice(...a),
      ...createLayerSlice(...a),
      ...createCatalogSlice(...a),
      ...createAnalysisSlice(...a),
      ...createResultSlice(...a),
      ...createInspectorSlice(...a),
      ...createGazetteerSlice(...a),
    })),
    {
      name: 'marsgis',
      version: 1,
      storage: createJSONStorage(() => createSafeStorage()),
      // Only durable UI prefs are persisted; all server data is re-fetched on load.
      partialize: (state) => ({
        camera: state.camera,
        basemapId: state.basemapId,
        panels: state.panels,
      }),
    },
  ),
);

/** Vanilla store handle for non-React consumers (LayerManager, picking, hooks). */
export const store = useStore;

export type { AppState };
