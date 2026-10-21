// Unit tests against the BUILT package (dist/), exactly as a consumer imports it.
// Run after `npm run build`:  npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import * as Cesium from 'cesium';
import * as mg from '../dist/index.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

test('package.json entry points resolve to real files', () => {
  const targets = [pkg.main, pkg.module, pkg.types, pkg.exports['.'].types, pkg.exports['.'].import,
    pkg.exports['./standalone']];
  for (const t of targets) assert.ok(existsSync(root + t), `missing ${t}`);
});

test('VERSION constant matches package.json', () => {
  assert.equal(mg.VERSION, pkg.version);
});

test('cesium is a peer dependency, never a runtime dependency', () => {
  assert.ok(pkg.peerDependencies?.cesium);
  assert.equal(pkg.dependencies?.cesium, undefined);
});

test('public API surface', () => {
  for (const name of ['MARS_RADII', 'installMarsEllipsoid', 'isMarsEllipsoidInstalled', 'marsViewerOptions',
    'applyMarsScene', 'BASEMAPS', 'basemapUrl', 'basemapProvider', 'MarsGlobe', 'createMarsGlobe',
    'setupMarsGlobe', 'MarsGlobeElement', 'defineMarsGlobe', 'VERSION']) {
    assert.ok(name in mg, `missing export ${name}`);
  }
});

test('installMarsEllipsoid sets Mars radii and is idempotent', () => {
  assert.equal(mg.isMarsEllipsoidInstalled(), false);
  mg.installMarsEllipsoid();
  const e = Cesium.Ellipsoid.default;
  assert.equal(e.radii.x, mg.MARS_RADII.equatorial);
  assert.equal(e.radii.y, mg.MARS_RADII.equatorial);
  assert.equal(e.radii.z, mg.MARS_RADII.polar);
  mg.installMarsEllipsoid();
  assert.equal(Cesium.Ellipsoid.default, e);
  assert.equal(mg.isMarsEllipsoidInstalled(), true);
});

test('marsViewerOptions strips Earth chrome and accepts overrides', () => {
  const o = mg.marsViewerOptions();
  assert.equal(o.baseLayer, false);
  assert.equal(o.geocoder, false);
  assert.equal(o.baseLayerPicker, false);
  assert.equal(o.skyAtmosphere, false);
  assert.equal(o.requestRenderMode, false);
  assert.ok(o.terrainProvider instanceof Cesium.EllipsoidTerrainProvider);
  const over = mg.marsViewerOptions({ requestRenderMode: true, timeline: true });
  assert.equal(over.requestRenderMode, true);
  assert.equal(over.timeline, true);
  assert.equal(over.geocoder, false);
});

test('basemapUrl builds the Trek WMTS template for every basemap', () => {
  for (const [id, b] of Object.entries(mg.BASEMAPS)) {
    assert.equal(b.id, id);
    const url = mg.basemapUrl(id);
    assert.match(url, /^https:\/\/trek\.nasa\.gov\/tiles\/Mars\/EQ\//);
    assert.ok(url.includes(b.product));
    assert.ok(url.endsWith(`/{z}/{y}/{x}.${b.ext}`));
  }
});

test('unknown basemap ids throw a descriptive error', () => {
  assert.throws(() => mg.basemapUrl('nope'), /Unknown basemap "nope"/);
  assert.throws(() => mg.basemapProvider('toString'), /Unknown basemap/);
});

test('basemapProvider uses the 2x1 geographic grid and per-product max zoom', () => {
  for (const [id, b] of Object.entries(mg.BASEMAPS)) {
    const p = mg.basemapProvider(id);
    assert.ok(p.tilingScheme instanceof Cesium.GeographicTilingScheme);
    assert.equal(p.tilingScheme.getNumberOfXTilesAtLevel(0), 2);
    assert.equal(p.tilingScheme.getNumberOfYTilesAtLevel(0), 1);
    assert.equal(p.minimumLevel, 0);
    assert.equal(p.maximumLevel, b.maxZoom);
  }
});

test('defineMarsGlobe is a safe no-op without customElements (SSR)', () => {
  assert.equal(typeof customElements, 'undefined');
  assert.doesNotThrow(() => mg.defineMarsGlobe());
});

test('standalone IIFE is small, excludes Cesium, and exposes window.MarsGlobe', () => {
  const file = root + 'dist/mars-globe.min.js';
  assert.ok(statSync(file).size < 10 * 1024, 'IIFE bundle should stay under 10 kB');
  const defined = new Map();
  const window = {
    Cesium,
    customElements: { get: (t) => defined.get(t), define: (t, c) => defined.set(t, c) },
  };
  window.globalThis = window;
  const ctx = vm.createContext({ ...window, window, HTMLElement: class {} });
  ctx.globalThis.Cesium = Cesium;
  vm.runInContext(readFileSync(file, 'utf8'), ctx);
  assert.equal(ctx.MarsGlobe.VERSION, pkg.version);
  assert.equal(typeof ctx.MarsGlobe.createMarsGlobe, 'function');
  assert.ok(defined.has('mars-globe'), 'standalone build auto-registers <mars-globe>');
});
