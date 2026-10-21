// createMarsGlobe: a self-contained, Mars-configured Cesium Viewer with
// switchable NASA Trek basemaps. The primary programmatic entry point.
import { ImageryLayer, Viewer } from 'cesium';
import { applyMarsScene, installMarsEllipsoid, marsViewerOptions } from './mars.js';
import { type BasemapId, basemapProvider } from './basemaps.js';

export interface MarsGlobeOptions {
  /** Initial basemap (default 'viking'). */
  defaultBasemap?: BasemapId;
  /** Keep the starfield skybox behind the globe (default true). */
  keepStars?: boolean;
  /** Extra Cesium Viewer options merged over the Mars defaults. */
  viewerOptions?: Partial<Viewer.ConstructorOptions>;
}

/** A Mars globe: owns a Cesium Viewer and the active basemap layer. */
export class MarsGlobe {
  readonly viewer: Viewer;
  private baseLayer: ImageryLayer | undefined;
  private currentBasemap: BasemapId;

  constructor(container: string | Element, options: MarsGlobeOptions = {}) {
    installMarsEllipsoid();
    this.viewer = new Viewer(container, marsViewerOptions(options.viewerOptions));
    applyMarsScene(this.viewer, { keepStars: options.keepStars });
    this.currentBasemap = options.defaultBasemap ?? 'viking';
    this.setBasemap(this.currentBasemap);
  }

  /** The active basemap id. */
  get basemap(): BasemapId {
    return this.currentBasemap;
  }

  /** Swap the basemap, keeping it at the bottom of the imagery stack. */
  setBasemap(id: BasemapId): void {
    const layers = this.viewer.imageryLayers;
    const next = layers.addImageryProvider(basemapProvider(id), 0);
    if (this.baseLayer) layers.remove(this.baseLayer, true);
    this.baseLayer = next;
    this.currentBasemap = id;
    this.viewer.scene.requestRender();
  }

  /** Destroy the underlying Cesium Viewer and free its WebGL context. */
  destroy(): void {
    if (!this.viewer.isDestroyed()) this.viewer.destroy();
  }
}

/** Create a Mars globe in `container` (an element or element id). */
export function createMarsGlobe(
  container: string | Element,
  options: MarsGlobeOptions = {},
): MarsGlobe {
  return new MarsGlobe(container, options);
}
