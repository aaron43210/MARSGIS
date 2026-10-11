// Store -> Cesium one-way sync. GlobeView calls attachStoreToCesium once with the viewer and
// the imperative managers; every store change is reconciled into Cesium here (and only here).
// UI never touches Cesium directly. Uses a single whole-state subscription (no extra middleware).
import type { Viewer } from 'cesium';
import { store } from '@/store';
import type { AppState, ImageryStackItem } from '@/store/types';
import { selectActiveResult, selectImageryStack } from '@/store/selectors';
import type { LayerManager } from '@/cesium/LayerManager';
import type { FootprintLayer } from '@/cesium/FootprintLayer';
import type { ResultOverlay } from '@/cesium/ResultOverlay';
import { flyToFeature, showFeatureMarker } from '@/cesium/markers';

interface CesiumManagers {
  viewer: Viewer;
  layerManager: LayerManager;
  footprintLayer: FootprintLayer;
  resultOverlay: ResultOverlay;
}

function stackEqual(a: ImageryStackItem[], b: ImageryStackItem[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!;
    const y = b[i]!;
    if (x.id !== y.id || x.show !== y.show || x.alpha !== y.alpha) return false;
  }
  return true;
}

export function attachStoreToCesium(managers: CesiumManagers): () => void {
  const { layerManager, footprintLayer, resultOverlay, viewer } = managers;

  // --- initial push ---
  let prevStack = selectImageryStack(store.getState());
  layerManager.syncImagery(prevStack);

  let prevObservations = store.getState().observations;
  footprintLayer.load(prevObservations);

  let prevSelected = store.getState().selectedObservationId;
  let prevHovered = store.getState().hoveredObservationId;
  footprintLayer.setSelected(prevSelected);
  footprintLayer.setHovered(prevHovered);

  let prevResultId = store.getState().activeResultId;
  let prevVisible = store.getState().overlayVisible;
  let prevOpacity = store.getState().overlayOpacity;
  void resultOverlay.setResult(
    selectActiveResult(store.getState())?.map_layer ?? null,
    prevVisible,
    prevOpacity,
  );

  let prevFeatureId = store.getState().selectedFeature?.id ?? null;

  const unsub = store.subscribe((state: AppState) => {
    // Imagery stack (basemap + overlays).
    const stack = selectImageryStack(state);
    if (!stackEqual(stack, prevStack)) {
      layerManager.syncImagery(stack);
      prevStack = stack;
    }

    // Footprints (observation set changed).
    if (state.observations !== prevObservations) {
      footprintLayer.load(state.observations);
      prevObservations = state.observations;
    }

    // Footprint selection / hover styling.
    if (state.selectedObservationId !== prevSelected) {
      footprintLayer.setSelected(state.selectedObservationId);
      if (state.selectedObservationId) footprintLayer.flyToObservation(state.selectedObservationId);
      prevSelected = state.selectedObservationId;
    }
    if (state.hoveredObservationId !== prevHovered) {
      footprintLayer.setHovered(state.hoveredObservationId);
      prevHovered = state.hoveredObservationId;
    }

    // Result overlay (active result or its visibility/opacity changed).
    const active = selectActiveResult(state);
    const activeId = active?.id ?? null;
    if (
      activeId !== prevResultId ||
      state.overlayVisible !== prevVisible ||
      state.overlayOpacity !== prevOpacity
    ) {
      void resultOverlay.setResult(active?.map_layer ?? null, state.overlayVisible, state.overlayOpacity);
      prevResultId = activeId;
      prevVisible = state.overlayVisible;
      prevOpacity = state.overlayOpacity;
    }

    // Gazetteer feature selection -> fly + marker.
    const featureId = state.selectedFeature?.id ?? null;
    if (featureId !== prevFeatureId) {
      if (state.selectedFeature) {
        showFeatureMarker(viewer, state.selectedFeature);
        flyToFeature(viewer, state.selectedFeature);
      }
      prevFeatureId = featureId;
    }
  });

  return unsub;
}
