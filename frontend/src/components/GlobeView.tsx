import { useEffect, useRef } from 'react';
import { Cartesian3, Math as CesiumMath, type Viewer } from 'cesium';
import { createMarsViewer, destroyMarsViewer } from '@/cesium/MarsViewer';
import { LayerManager } from '@/cesium/LayerManager';
import { buildTiledProvider } from '@/cesium/imageryProviders';
import { FootprintLayer } from '@/cesium/FootprintLayer';
import { ResultOverlay } from '@/cesium/ResultOverlay';
import { installPicking } from '@/cesium/picking';
import { attachStoreToCesium } from '@/hooks/useLayerSync';
import { store } from '@/store';
import { debounce } from '@/utils/debounce';

/**
 * Persistent React host for the single Cesium Viewer. The Viewer, managers and store<->Cesium
 * subscription are created once on mount and torn down on unmount. This component is never
 * conditionally unmounted, so the globe (and its WebGL context, camera and layers) survive mode
 * switches.
 */
export function GlobeView(): React.ReactElement {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const viewer = createMarsViewer(container);
    viewerRef.current = viewer;

    const layerManager = new LayerManager(viewer, buildTiledProvider);
    const footprintLayer = new FootprintLayer(viewer);
    const resultOverlay = new ResultOverlay(viewer);

    const detachStore = attachStoreToCesium({ viewer, layerManager, footprintLayer, resultOverlay });
    const detachPicking = installPicking(viewer, store, footprintLayer);

    // Start camera pulled back in outer space to create a stunning planetary zoom-in experience.
    const cam = store.getState().camera;
    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(cam.lon, cam.lat, 18_000_000),
      orientation: {
        heading: CesiumMath.toRadians(cam.heading),
        pitch: CesiumMath.toRadians(-90),
        roll: 0,
      },
    });

    // Smoothly fly down to layer observation altitude
    const introTimer = setTimeout(() => {
      if (!viewer.isDestroyed()) {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(cam.lon, cam.lat, Math.max(Math.min(cam.height, 3_500_000), 1_800_000)),
          duration: 2.2,
          complete: () => viewer.scene.requestRender(),
        });
      }
    }, 250);

    // Write camera back to the store (debounced) so persist + URL sync capture it.
    const writeCamera = debounce(() => {
      const carto = viewer.camera.positionCartographic;
      store.getState().setCamera({
        lon: CesiumMath.toDegrees(carto.longitude),
        lat: CesiumMath.toDegrees(carto.latitude),
        height: carto.height,
        heading: CesiumMath.toDegrees(viewer.camera.heading),
        pitch: CesiumMath.toDegrees(viewer.camera.pitch),
        roll: CesiumMath.toDegrees(viewer.camera.roll),
      });
    }, 300);
    const moveEndListener = (): void => writeCamera();
    viewer.camera.moveEnd.addEventListener(moveEndListener);

    viewer.scene.requestRender();

    return () => {
      clearTimeout(introTimer);
      writeCamera.cancel();
      viewer.camera.moveEnd.removeEventListener(moveEndListener);
      detachPicking();
      detachStore();
      resultOverlay.dispose();
      footprintLayer.destroy();
      layerManager.clear();
      destroyMarsViewer(viewer);
      viewerRef.current = null;
    };
  }, []);

  return <div className="globe-root" ref={containerRef} aria-label="Mars globe" role="application" />;
}
