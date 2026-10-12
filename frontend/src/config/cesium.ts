// Mars Cesium configuration: re-exports from mars-globe package.
import { Ion } from 'cesium';

// We don't use Cesium Ion — clear the default token so Cesium never attempts
// to reach api.cesium.com (which would fail in isolated/docker environments).
Ion.defaultAccessToken = '';

export {
  installMarsEllipsoid,
  isMarsEllipsoidInstalled,
  marsViewerOptions as viewerOptions,
  applyMarsScene as applyMarsSceneTweaks,
  MARS_RADII,
} from 'mars-globe';

