// mars-globe — a drop-in 3D Mars globe for CesiumJS.
// Mars ellipsoid, NASA Mars Trek basemaps, geographic tiling, no Ion token.
export {
  MARS_RADII,
  installMarsEllipsoid,
  isMarsEllipsoidInstalled,
  marsViewerOptions,
  applyMarsScene,
} from './mars';
export { BASEMAPS, basemapUrl, basemapProvider, type BasemapId, type BasemapDef } from './basemaps';
export { MarsGlobe, createMarsGlobe, type MarsGlobeOptions } from './globe';
export { setupMarsGlobe, type SetupMarsOptions } from './plugin';
export { MarsGlobeElement, defineMarsGlobe } from './webcomponent';

export const VERSION = '0.1.0';
