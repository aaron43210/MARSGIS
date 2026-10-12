// Create / tear down a Mars-configured Cesium Viewer. The Mars ellipsoid MUST already be
// installed (main.tsx calls installMarsEllipsoid before React mounts); we assert it here.
import { Viewer } from 'cesium';
import {
  installMarsEllipsoid,
  isMarsEllipsoidInstalled,
  marsViewerOptions,
  applyMarsScene,
} from 'mars-globe';

export function createMarsViewer(container: HTMLDivElement): Viewer {
  if (!isMarsEllipsoidInstalled()) {
    installMarsEllipsoid();
  }
  const viewer = new Viewer(container, marsViewerOptions());
  applyMarsScene(viewer);

  // Keep the attribution credits but prevent the default lightbox from grabbing clicks.
  const creditContainer = viewer.cesiumWidget.creditContainer as HTMLElement;
  creditContainer.style.display = 'none';

  return viewer;
}

export function destroyMarsViewer(viewer: Viewer | null | undefined): void {
  if (viewer && !viewer.isDestroyed()) viewer.destroy();
}
