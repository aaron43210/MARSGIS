// Ephemeral gazetteer marker + camera flight helpers.
import {
  Cartesian3,
  Color,
  LabelStyle,
  VerticalOrigin,
  Cartesian2,
  type Entity,
  type Viewer,
} from 'cesium';
import type { GazetteerFeature } from '@/store/types';

let markerEntity: Entity | null = null;

/** Height (m) to frame a feature of a given diameter, clamped to Mars-sensible bounds. */
function heightForFeature(diameterKm: number): number {
  const meters = Math.max(diameterKm, 5) * 1000 * 6;
  return Math.max(60_000, Math.min(5_000_000, meters));
}

/** Drop a single labelled marker at the feature; replaces any previous marker. */
export function showFeatureMarker(viewer: Viewer, feature: GazetteerFeature): void {
  removeFeatureMarker(viewer);
  markerEntity = viewer.entities.add({
    position: Cartesian3.fromDegrees(feature.lon, feature.lat),
    point: {
      pixelSize: 10,
      color: Color.fromCssColorString('#ffd38a'),
      outlineColor: Color.fromCssColorString('#5c2512'),
      outlineWidth: 2,
    },
    label: {
      text: feature.name,
      font: '13px system-ui, sans-serif',
      fillColor: Color.WHITE,
      outlineColor: Color.fromCssColorString('#05070b'),
      outlineWidth: 3,
      style: LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: VerticalOrigin.BOTTOM,
      pixelOffset: new Cartesian2(0, -14),
    },
  });
  viewer.scene.requestRender();
}

export function removeFeatureMarker(viewer: Viewer): void {
  if (markerEntity) {
    viewer.entities.remove(markerEntity);
    markerEntity = null;
    viewer.scene.requestRender();
  }
}

export function flyToFeature(viewer: Viewer, feature: GazetteerFeature): void {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(feature.lon, feature.lat, heightForFeature(feature.diameterKm)),
    duration: 1.4,
    complete: () => viewer.scene.requestRender(),
  });
}

export function flyToLonLat(viewer: Viewer, lon: number, lat: number, height: number): void {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(lon, lat, height),
    duration: 1.4,
    complete: () => viewer.scene.requestRender(),
  });
}
