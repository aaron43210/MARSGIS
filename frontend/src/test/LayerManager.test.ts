import { describe, it, expect, vi } from 'vitest';
import { LayerManager } from '@/cesium/LayerManager';
import type { IImageryLayer, IImageryLayers, ILayerManagerViewer } from '@/cesium/LayerManager';
import type { ImageryStackItem } from '@/store/types';
import type { MapLayer } from '@/types';

class FakeLayer implements IImageryLayer {
  show = true;
  alpha = 1;
  constructor(public provider: unknown) {}
}

/** Array-backed stand-in for Cesium's ImageryLayerCollection. Index 0 = bottom. */
class FakeCollection implements IImageryLayers {
  arr: FakeLayer[] = [];
  get length(): number {
    return this.arr.length;
  }
  get(i: number): IImageryLayer | undefined {
    return this.arr[i];
  }
  indexOf(layer: IImageryLayer): number {
    return this.arr.indexOf(layer as FakeLayer);
  }
  addImageryProvider(provider: unknown, index?: number): IImageryLayer {
    const layer = new FakeLayer(provider);
    if (index == null || index >= this.arr.length) this.arr.push(layer);
    else this.arr.splice(index, 0, layer);
    return layer;
  }
  remove(layer: IImageryLayer): boolean {
    const i = this.arr.indexOf(layer as FakeLayer);
    if (i >= 0) {
      this.arr.splice(i, 1);
      return true;
    }
    return false;
  }
  raise(layer: IImageryLayer): void {
    const i = this.arr.indexOf(layer as FakeLayer);
    if (i >= 0 && i < this.arr.length - 1) {
      const next = this.arr[i + 1]!;
      this.arr[i + 1] = this.arr[i]!;
      this.arr[i] = next;
    }
  }
  lower(layer: IImageryLayer): void {
    const i = this.arr.indexOf(layer as FakeLayer);
    if (i > 0) {
      const prev = this.arr[i - 1]!;
      this.arr[i - 1] = this.arr[i]!;
      this.arr[i] = prev;
    }
  }
}

function makeViewer(): { viewer: ILayerManagerViewer; coll: FakeCollection; render: ReturnType<typeof vi.fn> } {
  const coll = new FakeCollection();
  const render = vi.fn();
  const viewer: ILayerManagerViewer = { imageryLayers: coll, scene: { requestRender: render } };
  return { viewer, coll, render };
}

function item(id: string, show = true, alpha = 1): ImageryStackItem {
  return { id, layer: { id } as unknown as MapLayer, show, alpha };
}

function ids(coll: FakeCollection): string[] {
  return coll.arr.map((l) => (l.provider as { id: string }).id);
}

describe('LayerManager.syncImagery', () => {
  it('adds layers in bottom->top order and requests a render', () => {
    const { viewer, coll, render } = makeViewer();
    const lm = new LayerManager(viewer, (l) => ({ id: l.id }));
    lm.syncImagery([item('a'), item('b'), item('c')]);
    expect(ids(coll)).toEqual(['a', 'b', 'c']);
    expect(coll.length).toBe(3);
    expect(render).toHaveBeenCalled();
  });

  it('maps show and alpha (clamped) onto layers', () => {
    const { viewer, coll } = makeViewer();
    const lm = new LayerManager(viewer, (l) => ({ id: l.id }));
    lm.syncImagery([item('a', false, 0.3), item('b', true, 5)]);
    expect(coll.arr[0]!.show).toBe(false);
    expect(coll.arr[0]!.alpha).toBeCloseTo(0.3);
    expect(coll.arr[1]!.alpha).toBe(1); // clamped
  });

  it('removes layers no longer present', () => {
    const { viewer, coll } = makeViewer();
    const lm = new LayerManager(viewer, (l) => ({ id: l.id }));
    lm.syncImagery([item('a'), item('b'), item('c')]);
    lm.syncImagery([item('a'), item('c')]);
    expect(ids(coll)).toEqual(['a', 'c']);
  });

  it('reorders existing layers to match the desired order', () => {
    const { viewer, coll } = makeViewer();
    const lm = new LayerManager(viewer, (l) => ({ id: l.id }));
    lm.syncImagery([item('a'), item('b'), item('c')]);
    lm.syncImagery([item('c'), item('a'), item('b')]);
    expect(ids(coll)).toEqual(['c', 'a', 'b']);
  });

  it('does not recreate layers that persist across syncs', () => {
    const { viewer, coll } = makeViewer();
    const factory = vi.fn((l: MapLayer) => ({ id: l.id }));
    const lm = new LayerManager(viewer, factory);
    lm.syncImagery([item('a'), item('b')]);
    lm.syncImagery([item('a', true, 0.5), item('b')]);
    // 'a' and 'b' built once each; not rebuilt on the second sync.
    expect(factory).toHaveBeenCalledTimes(2);
    expect(coll.arr[0]!.alpha).toBeCloseTo(0.5);
  });

  it('clear() removes everything', () => {
    const { viewer, coll } = makeViewer();
    const lm = new LayerManager(viewer, (l) => ({ id: l.id }));
    lm.syncImagery([item('a'), item('b')]);
    lm.clear();
    expect(coll.length).toBe(0);
  });
});
