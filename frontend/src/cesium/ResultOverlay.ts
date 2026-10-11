// ResultOverlay: owns the single analysis-result imagery layer (always on top of the stack).
// Supports both tiled results (UrlTemplateImageryProvider over the backend zxy tile endpoint)
// and single-image results (SingleTileImageryProvider over the result bounds) transparently.
import { type ImageryLayer, type Viewer } from 'cesium';
import type { MapLayer } from '@/types';
import { buildImageryProvider } from './imageryProviders';

export class ResultOverlay {
  private readonly viewer: Viewer;
  private layer: ImageryLayer | null = null;
  private currentId: string | null = null;
  private visible = true;
  private opacity = 0.8;
  /** Monotonic token so a slow async add can be discarded if superseded. */
  private token = 0;

  constructor(viewer: Viewer) {
    this.viewer = viewer;
  }

  /** Set (or clear) the active result layer. Rebuilds only when the layer id changes. */
  async setResult(mapLayer: MapLayer | null, visible: boolean, opacity: number): Promise<void> {
    this.visible = visible;
    this.opacity = opacity;

    if (!mapLayer) {
      this.remove();
      return;
    }
    if (mapLayer.id === this.currentId && this.layer) {
      this.applyStyle();
      return;
    }

    const myToken = ++this.token;
    this.remove();
    this.currentId = mapLayer.id;

    let provider;
    try {
      provider = await buildImageryProvider(mapLayer);
    } catch (err) {
      // Leave the overlay empty on provider failure (e.g. offline tiles); surfaced via UI state.
      console.warn('ResultOverlay: failed to build provider', err);
      return;
    }
    if (myToken !== this.token) return; // superseded

    this.layer = this.viewer.imageryLayers.addImageryProvider(provider);
    this.applyStyle();
    this.viewer.scene.requestRender();
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.applyStyle();
  }

  setOpacity(opacity: number): void {
    this.opacity = opacity;
    this.applyStyle();
  }

  private applyStyle(): void {
    if (!this.layer) return;
    this.layer.show = this.visible;
    this.layer.alpha = Math.max(0, Math.min(1, this.opacity));
    this.viewer.imageryLayers.raiseToTop(this.layer);
    this.viewer.scene.requestRender();
  }

  private remove(): void {
    if (this.layer && this.viewer.imageryLayers.contains(this.layer)) {
      this.viewer.imageryLayers.remove(this.layer, true);
    }
    this.layer = null;
    this.currentId = null;
  }

  dispose(): void {
    this.token++;
    this.remove();
    this.viewer.scene.requestRender();
  }
}
