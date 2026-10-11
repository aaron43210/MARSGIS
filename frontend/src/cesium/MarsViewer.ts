// Create / tear down a Mars-configured Cesium Viewer. The Mars ellipsoid MUST already be
// installed (main.tsx calls installMarsEllipsoid before React mounts); we assert it here.
import { Viewer } from 'cesium';
import { applyMarsSceneTweaks, isMarsEllipsoidInstalled, viewerOptions } from '@/config/cesium';

export function createMarsViewer(container: HTMLDivElement): Viewer {
  if (!isMarsEllipsoidInstalled()) {
    throw new Error(
      'Mars ellipsoid not installed. Call installMarsEllipsoid() before creating any Viewer.',
    );
  }
  const viewer = new Viewer(container, viewerOptions());
  applyMarsSceneTweaks(viewer);

  // Keep the attribution credits but prevent the default lightbox from grabbing clicks.
  const creditContainer = viewer.cesiumWidget.creditContainer as HTMLElement;
  creditContainer.style.display = 'none';

  return viewer;
}

export function destroyMarsViewer(viewer: Viewer | null | undefined): void {
  if (viewer && !viewer.isDestroyed()) viewer.destroy();
}
