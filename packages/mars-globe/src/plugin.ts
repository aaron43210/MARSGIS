// CesiumJS plugin form: turn an EXISTING Viewer into Mars.
import type { Viewer } from 'cesium';
import { applyMarsScene, isMarsEllipsoidInstalled } from './mars';
import { type BasemapId, basemapProvider } from './basemaps';

export interface SetupMarsOptions {
  /** Basemap to add at the bottom of the stack (default 'viking'). */
  basemap?: BasemapId;
  keepStars?: boolean;
}

/**
 * Configure an existing Cesium ``Viewer`` for Mars: apply the dark scene,
 * disable Earth chrome, and add a Trek basemap.
 *
 * IMPORTANT: Cesium reads the ellipsoid at Viewer construction, so for correct
 * Mars geometry you must call {@link installMarsEllipsoid} BEFORE `new Viewer()`.
 * This emits a console warning if the viewer was built on a non-Mars ellipsoid.
 */
export function setupMarsGlobe(viewer: Viewer, options: SetupMarsOptions = {}): void {
  if (!isMarsEllipsoidInstalled()) {
    // eslint-disable-next-line no-console
    console.warn(
      '[mars-globe] Ellipsoid.default is not Mars-sized. Call installMarsEllipsoid() ' +
        'before constructing the Viewer so cameras/picking use Mars radii.',
    );
  }
  applyMarsScene(viewer, { keepStars: options.keepStars });
  viewer.imageryLayers.addImageryProvider(basemapProvider(options.basemap ?? 'viking'), 0);
  viewer.scene.requestRender();
}
