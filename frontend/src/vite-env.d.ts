/// <reference types="vite/client" />

// Global injected by vite `define` (build-time fallback for Cesium's base url).
declare const CESIUM_BASE_URL: string;

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_USE_MOCKS: string;
  readonly VITE_DEFAULT_BASEMAP: string;
  readonly VITE_CESIUM_BASE_URL?: string;
  readonly VITE_TREK_VIA_PROXY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Cesium ships its own types but has no bundled module declaration for the css import.
declare module 'cesium/Build/Cesium/Widgets/widgets.css';
declare module 'uplot/dist/uPlot.min.css';

interface Window {
  CESIUM_BASE_URL?: string;
}
