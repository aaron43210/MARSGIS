// LayerManager: the one-way reconciler from the Zustand store to Cesium's imagery stack.
// It is written against a MINIMAL viewer interface (not the concrete Viewer) so its diff/
// ordering/opacity logic is unit-testable in jsdom with a fake collection — no WebGL.
//
// It manages ONLY the layers it created (tracked by id). The result overlay (ResultOverlay)
// and footprints (FootprintLayer) manage their own Cesium objects, so this never clobbers them.
//
// NOTE: this module intentionally does NOT import Cesium, so it (and its test) stay WebGL-free.
// The caller injects a provider factory (buildTiledProvider in production).
import type { MapLayer } from '@/types';
import type { ImageryStackItem } from '@/store/types';

export interface IImageryLayer {
  show: boolean;
  alpha: number;
}

export interface IImageryLayers {
  readonly length: number;
  get(index: number): IImageryLayer | undefined;
  indexOf(layer: IImageryLayer): number;
  addImageryProvider(provider: unknown, index?: number): IImageryLayer;
  remove(layer: IImageryLayer, destroy?: boolean): boolean;
  raise(layer: IImageryLayer): void;
  lower(layer: IImageryLayer): void;
}

export interface ILayerManagerViewer {
  imageryLayers: IImageryLayers;
  scene: { requestRender(): void };
}

/** Factory from a MapLayer to a Cesium ImageryProvider; injectable for tests. */
type ProviderFactory = (layer: MapLayer) => unknown;

export class LayerManager {
  private readonly viewer: ILayerManagerViewer;
  private readonly providerFactory: ProviderFactory;
  private readonly byId = new Map<string, IImageryLayer>();

  constructor(viewer: ILayerManagerViewer, providerFactory: ProviderFactory) {
    this.viewer = viewer;
    this.providerFactory = providerFactory;
  }

  /** Ids currently managed, in bottom->top collection order. */
  managedOrder(): string[] {
    const entries = [...this.byId.entries()];
    entries.sort((a, b) => this.viewer.imageryLayers.indexOf(a[1]) - this.viewer.imageryLayers.indexOf(b[1]));
    return entries.map((e) => e[0]);
  }

  /** Reconcile the imagery stack to `items` (ordered bottom -> top). */
  syncImagery(items: ImageryStackItem[]): void {
    const layers = this.viewer.imageryLayers;
    const desiredIds = items.map((i) => i.id);
    const desiredSet = new Set(desiredIds);

    // 1. Remove layers no longer desired.
    for (const [id, layer] of [...this.byId.entries()]) {
      if (!desiredSet.has(id)) {
        layers.remove(layer, true);
        this.byId.delete(id);
      }
    }

    // 2. Add new layers; update show/alpha on all.
    items.forEach((item, index) => {
      let layer = this.byId.get(item.id);
      if (!layer) {
        const provider = this.providerFactory(item.layer);
        layer = layers.addImageryProvider(provider, index);
        this.byId.set(item.id, layer);
      }
      layer.show = item.show;
      layer.alpha = clamp01(item.alpha);
    });

    // 3. Reorder so collection order matches desired (bottom = index 0).
    this.reorder(desiredIds);

    this.viewer.scene.requestRender();
  }

  private reorder(desiredIds: string[]): void {
    const layers = this.viewer.imageryLayers;
    for (let target = 0; target < desiredIds.length; target++) {
      const id = desiredIds[target]!;
      const layer = this.byId.get(id);
      if (!layer) continue;
      let current = layers.indexOf(layer);
      let guard = 0;
      while (current > target && current > 0 && guard < 1000) {
        layers.lower(layer);
        current = layers.indexOf(layer);
        guard++;
      }
      while (current < target && guard < 1000) {
        layers.raise(layer);
        current = layers.indexOf(layer);
        guard++;
      }
    }
  }

  /** Remove every managed layer (teardown). */
  clear(): void {
    const layers = this.viewer.imageryLayers;
    for (const layer of this.byId.values()) layers.remove(layer, true);
    this.byId.clear();
    this.viewer.scene.requestRender();
  }
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}
