# MarsGIS — Frontend

Interactive **CesiumJS Mars globe** (the primary product) with four workspace modes rendered as
collapsible dock panels over a single, persistent globe canvas:

1. **Explore** — layer stack (verified NASA Trek basemaps + overlays)
2. **Observations** — browse/filter CRISM MTRDR observations; footprints draw as clickable polygons
3. **Analysis** — pick observation + MICA reference + SAM threshold → submit job → poll status
4. **Results** — add the result raster overlay (tiles + legend), inspect stats, export GeoTIFFs, and
   click a pixel to open the spectrum inspector

> **Scientific honesty:** every detection is a **candidate spectral match**, never a confirmed
> mineral deposit. The caveat is surfaced in the status bar, results panel and pixel inspector.
> Offline/mock data is labelled **SYNTHETIC** throughout and is never presented as real archive data.

## Stack

React 19 · TypeScript 5.9 · Vite 7 · CesiumJS 1.146 · Zustand 5 (+immer +persist) · uPlot · zod 4.

The stack is intentionally pinned to the mature line (not Vite 8 / plugin-react 6 / TS 7) so the
capstone reliably builds and runs; `typescript-eslint` requires TypeScript < 6.1.

## Mars configuration

- `installMarsEllipsoid()` sets `Ellipsoid.default` to Mars radii (3396190 / 3396190 / 3376200 m)
  in `main.tsx` **before** any Viewer is created.
- All imagery uses a `GeographicTilingScheme` (equirectangular, 2×1 tiles at z0) matching the
  verified NASA Trek EQ grid, so basemaps and result overlays co-register with no reprojection.
- Earth chrome (atmosphere, geocoder, base-layer picker, sun/moon) is disabled; no Cesium Ion token
  is used. Picking uses `camera.pickEllipsoid` (never `pickPosition`) because terrain is flat.

## Scripts

```bash
npm ci            # install (integrator runs this)
npm run dev       # dev server (proxies /api and /openapi.json to VITE_API_URL)
npm run build     # tsc -b && vite build  (copies Cesium Workers/Assets/Widgets to dist/cesium)
npm run preview   # preview the production build
npm run typecheck # tsc --noEmit
npm run lint      # eslint
npm run test      # vitest run (pure modules only: geo, format, store, LayerManager — no WebGL)
```

## Offline / CI mode

```bash
VITE_USE_MOCKS=true npm run dev
```

Serves every `/api` call from bundled **synthetic** fixtures in `src/data/*` (observations,
reference spectra, a sample result + overlay PNG, gazetteer features) and simulates a job advancing
`queued → running → succeeded`. No network, no Trek, no backend required. The globe degrades to a
dark base color if basemap tiles are unreachable.

## Environment

See `.env.example`. Key vars: `VITE_API_URL`, `VITE_USE_MOCKS`, `VITE_DEFAULT_BASEMAP`
(`viking | mola_clrshade | mola_dem | themis_dayir`), `VITE_TREK_VIA_PROXY`.

## Contract

Types come from the **frozen** hand-written mirror in `src/types/*` (owned by the shared-contract
unit; never edited here). The API client (`src/api/*`) targets the authoritative routes in
`contracts/openapi.yaml`; zod validates render-critical payloads (`src/api/validators.ts`).

## Architecture notes

- One persistent `GlobeView` owns the Cesium `Viewer` for its lifetime; it is never unmounted across
  modes, preserving the WebGL context and camera.
- A framework-agnostic `LayerManager` reconciles the imagery stack **one-way** from the Zustand
  store (store is the source of truth; UI never touches Cesium directly). It is unit-tested with a
  fake collection — no WebGL.
- The four verified Trek basemaps (Viking jpg, MOLA ClrShade jpg, MOLA-DEM png, THEMIS Day IR png)
  ship as a hardcoded fallback; the full catalogue is fetched from `GET /api/layers`.

The `Dockerfile`, `.dockerignore` and `nginx/` config are owned by the infra unit (not created here).
