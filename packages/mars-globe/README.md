# mars-globe

A drop-in **3D Mars globe for CesiumJS** — the Mars ellipsoid, NASA Mars Trek
basemaps, and the correct geographic tiling, configured for you. No Cesium Ion
token required.

Setting Cesium up for Mars (overriding the ellipsoid to 3,396 km × 3,376 km,
removing Earth atmosphere/skybox/geocoder, and wiring the NASA Trek tile scheme)
is fiddly and poorly documented. This package does it in one line, three ways:
an **NPM module**, a **`<mars-globe>` Web Component**, and a **CesiumJS plugin**.

> Extracted from the open-source [MarsGIS](https://github.com/aaron43210/MARSGIS)
> project, where it powers the live Mars map.

## Install

```bash
npm install mars-globe cesium
```

`cesium` is a **peer dependency** (not bundled) — install the Cesium version your
app uses. Cesium also needs its static assets available: set
`window.CESIUM_BASE_URL` and load `cesium/Build/Cesium/Widgets/widgets.css`
(standard Cesium setup; your bundler plugin or a copy step handles this).

## Use it (3 ways)

### 1. NPM module — React / Vue / Svelte / plain JS

```js
import { createMarsGlobe } from 'mars-globe';

const globe = createMarsGlobe(document.getElementById('map'), {
  defaultBasemap: 'viking', // 'viking' | 'mola' | 'mola-dem' | 'themis'
});

globe.setBasemap('mola');      // switch basemap at runtime
globe.viewer;                  // the underlying Cesium Viewer (full API)
globe.destroy();               // tear down + free the WebGL context
```

### 2. Web Component — any HTML page

```html
<script type="module">
  import { defineMarsGlobe } from 'mars-globe';
  defineMarsGlobe();
</script>

<mars-globe basemap="viking" style="display:block; width:100vw; height:100vh;"></mars-globe>
```

Or with the standalone build + a plain script tag (Cesium loaded first):

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/cesium@1.146.0/Build/Cesium/Widgets/widgets.css" />
<script>window.CESIUM_BASE_URL = 'https://cdn.jsdelivr.net/npm/cesium@1.146.0/Build/Cesium/';</script>
<script src="https://cdn.jsdelivr.net/npm/cesium@1.146.0/Build/Cesium/Cesium.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mars-globe@1/dist/mars-globe.min.js"></script>

<mars-globe basemap="mola" style="display:block; width:100vw; height:100vh;"></mars-globe>
```

### 3. CesiumJS plugin — an existing Viewer

```js
import { Viewer } from 'cesium';
import { installMarsEllipsoid, setupMarsGlobe } from 'mars-globe';

installMarsEllipsoid();                 // MUST run before the Viewer is created
const viewer = new Viewer('cesiumContainer');
setupMarsGlobe(viewer, { basemap: 'viking' });
```

## Basemaps

| id | layer |
|----|-------|
| `viking` | Viking MDIM 2.1 color mosaic (232 m) |
| `mola` | MOLA color shaded relief (463 m) |
| `mola-dem` | MOLA colorized elevation (visual, 463 m) |
| `themis` | THEMIS day IR (100 m) |

All are the global equirectangular NASA Trek grid (2×1 tiles at level 0), served
live from `trek.nasa.gov`.

## API

- `createMarsGlobe(container, options?) => MarsGlobe` — `{ defaultBasemap?, keepStars?, viewerOptions? }`.
- `MarsGlobe` — `.viewer`, `.basemap`, `.setBasemap(id)`, `.destroy()`.
- `setupMarsGlobe(viewer, { basemap?, keepStars? })` — configure an existing Viewer.
- `installMarsEllipsoid()` / `isMarsEllipsoidInstalled()`.
- `marsViewerOptions(overrides?)`, `applyMarsScene(viewer, { keepStars? })`.
- `basemapProvider(id)`, `basemapUrl(id)`, `BASEMAPS`.
- `defineMarsGlobe(tagName?)`, `MarsGlobeElement`.
- `MARS_RADII`, `VERSION`.

## Notes

- `requestRenderMode` defaults **off** so async tile loads never leave the globe
  on a blank first frame. Pass `viewerOptions: { requestRenderMode: true }` if you
  drive `scene.requestRender()` yourself.
- Safe to import during SSR / in Node (nothing touches the DOM until you create
  a globe or call `defineMarsGlobe()` in the browser).
- Coordinates are Mars IAU 2000 degrees (east-positive longitude).
- Imagery is NASA/JPL/USGS — Mars Trek, streamed live and **not** redistributed
  by this package.

## Development

```bash
npm run build          # ESM + types + standalone IIFE into dist/
npm test               # unit tests against dist/
npm run test:browser   # headless Chrome, all 3 usage modes (needs network for Trek tiles)
```

## License

MIT © AARON R
