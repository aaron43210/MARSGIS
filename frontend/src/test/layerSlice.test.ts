import { describe, it, expect, beforeEach } from 'vitest';
import { useStore } from '@/store';
import { selectImageryStack } from '@/store/selectors';
import type { MapLayer } from '@/types';

function makeLayer(id: string, opacity = 0.8, defaultVisible = true): MapLayer {
  return {
    id,
    default_visible: defaultVisible,
    style: { opacity },
  } as unknown as MapLayer;
}

describe('layerSlice reducers', () => {
  beforeEach(() => {
    useStore.setState({ overlays: [] });
  });

  it('addOverlay seeds order/visible/opacity from the MapLayer', () => {
    useStore.getState().addOverlay(makeLayer('ctx1', 0.5, true));
    const [entry] = useStore.getState().overlays;
    expect(entry).toBeDefined();
    expect(entry!.id).toBe('ctx1');
    expect(entry!.order).toBe(0);
    expect(entry!.opacity).toBeCloseTo(0.5);
    expect(entry!.visible).toBe(true);
  });

  it('addOverlay ignores duplicates', () => {
    const l = makeLayer('ctx1');
    useStore.getState().addOverlay(l);
    useStore.getState().addOverlay(l);
    expect(useStore.getState().overlays).toHaveLength(1);
  });

  it('reorderOverlay renumbers order contiguously', () => {
    const s = useStore.getState();
    s.addOverlay(makeLayer('a'));
    s.addOverlay(makeLayer('b'));
    s.addOverlay(makeLayer('c'));
    useStore.getState().reorderOverlay('c', 0);
    const order = useStore.getState().overlays.map((o) => o.id);
    expect(order).toEqual(['c', 'a', 'b']);
    expect(useStore.getState().overlays.map((o) => o.order)).toEqual([0, 1, 2]);
  });

  it('removeOverlay renumbers order', () => {
    const s = useStore.getState();
    s.addOverlay(makeLayer('a'));
    s.addOverlay(makeLayer('b'));
    s.addOverlay(makeLayer('c'));
    useStore.getState().removeOverlay('b');
    expect(useStore.getState().overlays.map((o) => o.id)).toEqual(['a', 'c']);
    expect(useStore.getState().overlays.map((o) => o.order)).toEqual([0, 1]);
  });

  it('setLayerVisible / setLayerOpacity update and clamp', () => {
    useStore.getState().addOverlay(makeLayer('a'));
    useStore.getState().setLayerVisible('a', false);
    useStore.getState().setLayerOpacity('a', 2);
    const entry = useStore.getState().overlays.find((o) => o.id === 'a');
    expect(entry!.visible).toBe(false);
    expect(entry!.opacity).toBe(1);
  });

  it('selectImageryStack puts the basemap at the bottom, overlays above', () => {
    useStore.setState({
      overlays: [],
      baseLayers: [makeLayer('viking')],
      basemapId: 'viking',
    });
    useStore.getState().addOverlay(makeLayer('ctx'));
    const stack = selectImageryStack(useStore.getState());
    expect(stack[0]!.id).toBe('viking');
    expect(stack[1]!.id).toBe('ctx');
  });
});
