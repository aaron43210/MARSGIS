// Typed, validated access to import.meta.env. Centralizes all VITE_* reads so the rest
// of the app never touches import.meta.env directly.

function readBool(value: string | undefined, fallback: boolean): boolean {
  if (value == null) return fallback;
  return value === 'true' || value === '1';
}

const rawApiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
// Normalize: drop a single trailing slash so `${apiUrl}/api/...` never doubles up.
const apiUrl = rawApiUrl === '/' ? '' : rawApiUrl.replace(/\/$/, '');

export const env = {
  /** Base URL for the backend. '' means same-origin (prod behind nginx). */
  apiUrl,
  /** Serve all /api data from bundled synthetic fixtures (offline/CI). */
  useMocks: readBool(import.meta.env.VITE_USE_MOCKS, false),
  /** Default base layer id on first load. */
  defaultBasemap: import.meta.env.VITE_DEFAULT_BASEMAP ?? 'viking',
  /** Where Cesium's copied static assets are served from. */
  cesiumBaseUrl: import.meta.env.VITE_CESIUM_BASE_URL ?? '/cesium',
  /** Route Trek tiles through the /trek proxy instead of trek.nasa.gov. */
  trekViaProxy: readBool(import.meta.env.VITE_TREK_VIA_PROXY, false),
} as const;
