// Mars Cesium configuration: the ellipsoid installer (MUST run before any Viewer) and
// the Viewer option presets that strip all Earth-specific chrome.
import {
  Ellipsoid,
  EllipsoidTerrainProvider,
  Color,
  type Viewer,
} from 'cesium';
import { MARS_RADII } from './constants';

let marsInstalled = false;

/**
 * Set Cesium's global default ellipsoid to Mars radii. This is the supported global hook
 * (Cesium >= 1.106) and MUST be called before any Viewer/Camera/picking is constructed so
 * that every downstream computation uses Mars radii instead of WGS84.
 */
export function installMarsEllipsoid(): void {
  if (marsInstalled) return;
  const mars = new Ellipsoid(MARS_RADII.equatorial, MARS_RADII.equatorial, MARS_RADII.polar);
  Ellipsoid.default = mars;
  marsInstalled = true;
}

/** True once installMarsEllipsoid() has run and Ellipsoid.default is Mars-sized. */
export function isMarsEllipsoidInstalled(): boolean {
  return (
    marsInstalled &&
    Math.round(Ellipsoid.default.maximumRadius) === MARS_RADII.equatorial
  );
}

/** Viewer options: no Earth geocoder, no base-layer picker, no atmosphere, request-render mode on. */
export function viewerOptions(): Viewer.ConstructorOptions {
  return {
    baseLayer: false, // we add imagery ourselves via LayerManager
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    skyAtmosphere: false,
    // Continuous rendering: requestRenderMode can leave the globe on an empty
    // (black) first frame when imagery/tiles finish loading asynchronously and
    // nothing re-triggers a render (mouse-move updates the coordinate read-out
    // but does not re-render). A single Mars globe renders cheaply, so render
    // every frame for correctness.
    requestRenderMode: false,
    terrainProvider: new EllipsoidTerrainProvider(),
  };
}

/** Post-construction scene tweaks: dark Mars globe, no sun/moon/atmosphere, keep starfield. */
export function applyMarsSceneTweaks(viewer: Viewer): void {
  const scene = viewer.scene;
  const globe = scene.globe;
  globe.showGroundAtmosphere = false;
  globe.enableLighting = false;
  globe.baseColor = Color.fromCssColorString('#7c3f25'); // Martian ferric oxide / rust red
  globe.tileCacheSize = 1000;
  if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
  if (scene.sun) scene.sun.show = false;
  if (scene.moon) scene.moon.show = false;
  // Keep the starfield skybox for spatial reference.
  scene.fog.enabled = false;
  scene.backgroundColor = Color.fromCssColorString('#05070b');
  // No Cesium Ion token is used anywhere (custom ellipsoid + Trek imagery only).
}
