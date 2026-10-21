// Real-browser smoke test for all three usage modes (needs network: tiles stream
// live from trek.nasa.gov). Serves the package root, drives headless Chrome.
//   npm run build && npm run test:browser
// Uses installed Google Chrome; set CHROME_PATH to use another Chromium binary.
// Set SCREENSHOT_DIR to save a PNG per page for a visual check.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = fileURLToPath(new URL('../..', import.meta.url));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.wasm': 'application/wasm', '.xml': 'application/xml', '.svg': 'image/svg+xml' };

const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname));
  try {
    const body = await readFile(join(root, path));
    res.writeHead(200, { 'content-type': TYPES[extname(path)] ?? 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }),
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});

let failures = 0;
function check(label, ok, detail = '') {
  console.log(`${ok ? '  ✔' : '  ✖'} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

async function openPage(file) {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  const errors = [];
  const tiles = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('response', (r) => {
    if (r.url().startsWith('https://trek.nasa.gov/')) tiles.push({ url: r.url(), status: r.status() });
  });
  await page.goto(`${base}/test/browser/${file}`);
  const waitTile = async (product) => {
    const deadline = Date.now() + 45_000;
    while (Date.now() < deadline) {
      if (tiles.some((t) => t.url.includes(product) && t.status === 200)) return true;
      await page.waitForTimeout(250);
    }
    return false;
  };
  const shot = async (name) => {
    if (!process.env.SCREENSHOT_DIR) return;
    await mkdir(process.env.SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: join(process.env.SCREENSHOT_DIR, `${name}.png`) });
  };
  return { page, errors, tiles, waitTile, shot };
}

const P = { viking: 'Viking_MDIM21', mola: 'MOLA_ClrShade', themis: 'THEMIS_DayIR' };

console.log('Mode 1 — createMarsGlobe (native ESM, import map)');
{
  const { page, errors, waitTile, shot } = await openPage('esm.html');
  await page.waitForFunction(() => window.__test, null, { timeout: 30_000 });
  const r = await page.evaluate(() => ({ radius: __test.radius(), expected: __test.expected,
    installed: __test.installed(), layers: __test.layers(), basemap: __test.globe.basemap }));
  check('scene globe uses Mars ellipsoid', r.radius === r.expected, `${r.radius} m`);
  check('isMarsEllipsoidInstalled()', r.installed);
  check('exactly one basemap layer', r.layers === 1);
  check('default basemap is viking', r.basemap === 'viking');
  check('Viking tiles stream from Trek (HTTP 200)', await waitTile(P.viking));
  await page.waitForFunction(() => __test.viewer.scene.globe.tilesLoaded, null, { timeout: 60_000 });
  await shot('mode1-esm-viking');
  const s = await page.evaluate(() => { __test.globe.setBasemap('mola'); return { layers: __test.layers(), basemap: __test.globe.basemap }; });
  check('setBasemap swaps (still one layer)', s.layers === 1 && s.basemap === 'mola');
  check('MOLA tiles stream after switch', await waitTile(P.mola));
  const bad = await page.evaluate(() => { try { __test.globe.setBasemap('nope'); return null; } catch (e) { return e.message; } });
  check('invalid basemap throws a clear error', /Unknown basemap/.test(bad ?? ''), bad ?? 'no error');
  const d = await page.evaluate(() => { __test.globe.destroy(); __test.globe.destroy(); return __test.viewer.isDestroyed(); });
  check('destroy() frees the viewer (idempotent)', d);
  check('no uncaught page errors', errors.length === 0, errors.join(' | '));
  await page.close();
}

console.log('Mode 3 — setupMarsGlobe on an existing Viewer');
{
  const { page, errors, waitTile, shot } = await openPage('esm.html?mode=plugin');
  await page.waitForFunction(() => window.__test, null, { timeout: 30_000 });
  const r = await page.evaluate(() => ({ radius: __test.radius(), expected: __test.expected, layers: __test.layers() }));
  check('viewer built on Mars ellipsoid', r.radius === r.expected, `${r.radius} m`);
  check('one basemap layer added', r.layers === 1);
  check('MOLA tiles stream from Trek', await waitTile(P.mola));
  await page.waitForFunction(() => __test.viewer.scene.globe.tilesLoaded, null, { timeout: 60_000 });
  await shot('mode3-plugin-mola');
  check('no uncaught page errors', errors.length === 0, errors.join(' | '));
  await page.close();
}

console.log('Mode 2 — <mars-globe> Web Component (ES module)');
{
  const { page, errors, waitTile, shot } = await openPage('webcomponent.html');
  await page.waitForFunction(() => document.querySelector('mars-globe')?.marsGlobe, null, { timeout: 30_000 });
  const r = await page.evaluate(() => {
    const g = document.querySelector('mars-globe').marsGlobe;
    return { basemap: g.basemap, radius: g.viewer.scene.globe.ellipsoid.maximumRadius, h: g.viewer.canvas.clientHeight };
  });
  check('element creates a globe from basemap attribute', r.basemap === 'themis');
  check('globe uses Mars ellipsoid', r.radius === 3396190, `${r.radius} m`);
  check('canvas fills the element', r.h === 600, `${r.h}px`);
  check('THEMIS tiles stream from Trek', await waitTile(P.themis));
  await page.waitForFunction(() => document.querySelector('mars-globe').marsGlobe.viewer.scene.globe.tilesLoaded, null, { timeout: 60_000 });
  await shot('mode2-webcomponent-themis');
  const a = await page.evaluate(() => {
    const el = document.querySelector('mars-globe');
    el.setAttribute('basemap', 'viking');
    const afterValid = el.marsGlobe.basemap;
    el.setAttribute('basemap', 'not-a-basemap');
    return { afterValid, afterInvalid: el.marsGlobe.basemap };
  });
  check('basemap attribute change switches layer', a.afterValid === 'viking');
  check('invalid attribute value is ignored', a.afterInvalid === 'viking');
  check('Viking tiles stream after attribute change', await waitTile(P.viking));
  const gone = await page.evaluate(() => {
    const el = document.querySelector('mars-globe');
    const v = el.marsGlobe.viewer;
    el.remove();
    return { destroyed: v.isDestroyed(), globe: el.marsGlobe === undefined, children: el.children.length };
  });
  check('removing the element destroys the viewer', gone.destroyed && gone.globe && gone.children === 0);
  check('no uncaught page errors', errors.length === 0, errors.join(' | '));
  await page.close();
}

console.log('Mode 2b — standalone IIFE via <script> (window.Cesium)');
{
  const { page, errors, waitTile, shot } = await openPage('standalone.html');
  await page.waitForFunction(() => document.querySelector('mars-globe')?.marsGlobe, null, { timeout: 30_000 });
  const r = await page.evaluate(() => ({ version: window.MarsGlobe?.VERSION,
    basemap: document.querySelector('mars-globe').marsGlobe.basemap }));
  check('window.MarsGlobe global exposed', typeof r.version === 'string', r.version);
  check('<mars-globe> auto-registered and rendered', r.basemap === 'mola');
  check('MOLA tiles stream from Trek', await waitTile(P.mola));
  await page.waitForFunction(() => document.querySelector('mars-globe').marsGlobe.viewer.scene.globe.tilesLoaded, null, { timeout: 60_000 });
  await shot('mode2b-standalone-mola');
  check('no uncaught page errors', errors.length === 0, errors.join(' | '));
  await page.close();
}

await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll browser checks passed');
process.exit(failures ? 1 : 0);
