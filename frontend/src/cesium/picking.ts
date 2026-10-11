// ScreenSpaceEventHandler wiring: hover lon/lat readout + footprint hover highlight, footprint
// selection on click, and result-pixel inspection on click in results mode.
//
// Uses camera.pickEllipsoid (NOT scene.pickPosition): with a flat EllipsoidTerrainProvider there
// is no depth geometry for pickPosition, but pickEllipsoid returns an exact lon/lat on the Mars
// ellipsoid.
import {
  Cartographic,
  Ellipsoid,
  Math as CesiumMath,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  type Cartesian2,
  type Viewer,
} from 'cesium';
import type { StoreApi } from 'zustand';
import type { AppState } from '@/store/types';
import type { FootprintLayer } from './FootprintLayer';
import { normalizeLon180, clampLat } from './geo';

function toLonLat(viewer: Viewer, position: Cartesian2): { lon: number; lat: number } | null {
  const cartesian = viewer.camera.pickEllipsoid(position, Ellipsoid.default);
  if (!cartesian) return null;
  const carto = Ellipsoid.default.cartesianToCartographic(cartesian, new Cartographic());
  return {
    lon: normalizeLon180(CesiumMath.toDegrees(carto.longitude)),
    lat: clampLat(CesiumMath.toDegrees(carto.latitude)),
  };
}

/** Returns true if the picked object is a footprint entity, yielding its observation id. */
function pickedObservationId(picked: unknown): string | null {
  if (picked && typeof picked === 'object' && 'id' in picked) {
    const entity = picked.id;
    if (entity && typeof entity === 'object' && 'id' in entity) {
      const id = entity.id;
      if (typeof id === 'string') return id;
    }
  }
  return null;
}

export function installPicking(
  viewer: Viewer,
  store: StoreApi<AppState>,
  footprints: FootprintLayer,
): () => void {
  const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);

  handler.setInputAction((movement: ScreenSpaceEventHandler.MotionEvent) => {
    const lonlat = toLonLat(viewer, movement.endPosition);
    store.getState().setHover(lonlat);
    const picked: unknown = viewer.scene.pick(movement.endPosition);
    const obsId = pickedObservationId(picked);
    footprints.setHovered(obsId);
    store.getState().hoverObservation(obsId);
  }, ScreenSpaceEventType.MOUSE_MOVE);

  handler.setInputAction((click: ScreenSpaceEventHandler.PositionedEvent) => {
    const picked: unknown = viewer.scene.pick(click.position);
    const obsId = pickedObservationId(picked);
    const state = store.getState();
    if (obsId) {
      state.selectObservation(obsId);
      footprints.setSelected(obsId);
      return;
    }
    // Empty-space click in results mode with an active result -> inspect the pixel.
    if (state.mode === 'results' && state.activeResultId) {
      const lonlat = toLonLat(viewer, click.position);
      if (lonlat) {
        void state.inspectPixel(state.activeResultId, lonlat.lon, lonlat.lat);
      }
    }
  }, ScreenSpaceEventType.LEFT_CLICK);

  return () => handler.destroy();
}
