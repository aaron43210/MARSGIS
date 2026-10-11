// Mars body configuration for CesiumJS: ellipsoid, viewer options, scene tweaks.
// The ellipsoid MUST be installed before any Viewer/Camera is constructed.
import { Color, Ellipsoid, EllipsoidTerrainProvider, type Viewer } from 'cesium';

/** Mars IAU 2000 reference radii (metres): equatorial / polar. */
export const MARS_RADII = { equatorial: 3_396_190, polar: 3_376_200 } as const;

let installed = false;

/**
 * Set Cesium's global default ellipsoid to Mars radii. Supported global hook
 * (Cesium >= 1.106); must run BEFORE constructing any Viewer so cameras,
 * picking and tiling all use Mars radii instead of WGS84. Idempotent.
 */
export function installMarsEllipsoid(): void {
  if (installed) return;
  Ellipsoid.default = new Ellipsoid(MARS_RADII.equatorial, MARS_RADII.equatorial, MARS_RADII.polar);
  installed = true;
}

/** True once {@link installMarsEllipsoid} has made the default ellipsoid Mars-sized. */
export function isMarsEllipsoidInstalled(): boolean {
  return installed && Math.round(Ellipsoid.default.maximumRadius) === MARS_RADII.equatorial;
}

/**
 * Cesium Viewer options with all Earth-specific chrome removed (geocoder,
 * base-layer picker, atmosphere, sun/moon). `baseLayer:false` because the Mars
 * basemap is added explicitly. `requestRenderMode` defaults OFF so async tile
 * loads never leave the globe on a blank first frame; override if you drive
 * `scene.requestRender()` yourself.
 */
export function marsViewerOptions(
  overrides: Partial<Viewer.ConstructorOptions> = {},
): Viewer.ConstructorOptions {
  return {
    baseLayer: false,
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
    requestRenderMode: false,
    terrainProvider: new EllipsoidTerrainProvider(),
    ...overrides,
  };
}

/** Post-construction scene tweaks: dark Mars globe, no sun/moon/atmosphere. */
export function applyMarsScene(viewer: Viewer, options: { keepStars?: boolean } = {}): void {
  const { scene } = viewer;
  const { globe } = scene;
  globe.showGroundAtmosphere = false;
  globe.enableLighting = false;
  globe.baseColor = Color.fromCssColorString('#1a1410'); // dark basalt where tiles are missing
  if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
  if (scene.sun) scene.sun.show = false;
  if (scene.moon) scene.moon.show = false;
  if (scene.skyBox) scene.skyBox.show = options.keepStars ?? true;
  scene.fog.enabled = false;
  scene.backgroundColor = Color.fromCssColorString('#05070b');
  // No Cesium Ion token is used (custom ellipsoid + NASA Trek imagery only).
}
