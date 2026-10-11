import type { AppState, ImageryStackItem } from './types';
import type { AnalysisResult, MapLayer, ObservationSummary } from '@/types';

/**
 * The imagery stack LayerManager reconciles, ordered bottom -> top:
 *   [ selected basemap, ...overlays (by order) ].
 * The result overlay is NOT included here — ResultOverlay manages it separately on top.
 */
export function selectImageryStack(state: AppState): ImageryStackItem[] {
  const items: ImageryStackItem[] = [];
  const base: MapLayer | undefined =
    state.baseLayers.find((l) => l.id === state.basemapId) ?? state.baseLayers[0];
  if (base) items.push({ id: base.id, layer: base, show: true, alpha: 1 });

  const overlays = [...state.overlays].sort((a, b) => a.order - b.order);
  for (const o of overlays) {
    items.push({ id: o.id, layer: o.layer, show: o.visible, alpha: o.opacity });
  }
  return items;
}

export function selectActiveResult(state: AppState): AnalysisResult | null {
  return state.activeResultId ? (state.results[state.activeResultId] ?? null) : null;
}

export function selectSelectedObservation(state: AppState): ObservationSummary | null {
  const id = state.selectedObservationId;
  if (!id) return null;
  return state.observations.find((o) => o.id === id) ?? null;
}

export interface FootprintStyleState {
  selectedId: string | null;
  hoveredId: string | null;
}
export function selectFootprintStyleState(state: AppState): FootprintStyleState {
  return { selectedId: state.selectedObservationId, hoveredId: state.hoveredObservationId };
}
