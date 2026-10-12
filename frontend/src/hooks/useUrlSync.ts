import { useEffect } from 'react';
import { useStore } from '@/store';
import type { WorkspaceMode } from '@/store/types';
import { debounce } from '@/utils/debounce';

const MODES: WorkspaceMode[] = ['explore', 'observations', 'analysis', 'results'];

function parseNum(v: string | null): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * Two-way deep-link sync with the URL query (no react-router — the globe never unmounts).
 * On mount: hydrate mode/obs/result/camera from ?mode&obs&result&lon&lat&h.
 * Thereafter: mirror those fields back into the URL via replaceState (debounced).
 */
export function useUrlSync(): void {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const state = useStore.getState();

    const mode = params.get('mode');
    if (mode && (MODES as string[]).includes(mode)) state.setMode(mode as WorkspaceMode);

    const lon = parseNum(params.get('lon'));
    const lat = parseNum(params.get('lat'));
    const h = parseNum(params.get('h'));
    if (lon != null && lat != null) {
      // Prevent underground clipping when h is zero/subterranean from test query strings (e.g. h=2)
      const height = h != null && h >= 10_000 ? h : state.camera.height;
      state.setCamera({ ...state.camera, lon, lat, height });
    }

    const obs = params.get('obs');
    if (obs) state.selectObservation(obs);

    const result = params.get('result');
    if (result) void state.loadResult(result);
  }, []);

  useEffect(() => {
    const write = debounce(() => {
      const s = useStore.getState();
      const params = new URLSearchParams();
      params.set('mode', s.mode);
      if (s.selectedObservationId) params.set('obs', s.selectedObservationId);
      if (s.activeResultId) params.set('result', s.activeResultId);
      params.set('lon', s.camera.lon.toFixed(3));
      params.set('lat', s.camera.lat.toFixed(3));
      params.set('h', Math.round(s.camera.height).toString());
      const next = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState(null, '', next);
    }, 400);

    const unsub = useStore.subscribe(() => write());
    return () => {
      unsub();
      write.cancel();
    };
  }, []);
}
