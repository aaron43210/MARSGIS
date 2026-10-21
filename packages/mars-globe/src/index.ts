// mars-globe — a drop-in 3D Mars globe for CesiumJS.
// Mars ellipsoid, NASA Mars Trek basemaps, geographic tiling, no Ion token.
export {
  MARS_RADII,
  installMarsEllipsoid,
  isMarsEllipsoidInstalled,
  marsViewerOptions,
  applyMarsScene,
} from './mars.js';
export { BASEMAPS, basemapUrl, basemapProvider, type BasemapId, type BasemapDef } from './basemaps.js';
export { MarsGlobe, createMarsGlobe, type MarsGlobeOptions } from './globe.js';
export { setupMarsGlobe, type SetupMarsOptions } from './plugin.js';
export { MarsGlobeElement, defineMarsGlobe } from './webcomponent.js';

export const VERSION = '1.0.0';
