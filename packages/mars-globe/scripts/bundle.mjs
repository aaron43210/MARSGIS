// Build the standalone IIFE bundle for plain <script> / CDN usage.
// Cesium is NOT bundled: the bare `cesium` import is mapped to the global
// `window.Cesium` that the page must load first (keeps the bundle small).
import esbuild from 'esbuild';

const cesiumGlobal = {
  name: 'cesium-global',
  setup(build) {
    build.onResolve({ filter: /^cesium$/ }, () => ({ path: 'cesium', namespace: 'cesium-global' }));
    build.onLoad({ filter: /.*/, namespace: 'cesium-global' }, () => ({
      contents: 'module.exports = (globalThis.Cesium || window.Cesium);',
      loader: 'js',
    }));
  },
};

await esbuild.build({
  entryPoints: ['src/standalone.ts'],
  bundle: true,
  format: 'iife',
  globalName: 'MarsGlobe',
  outfile: 'dist/mars-globe.min.js',
  minify: true,
  sourcemap: true,
  target: ['es2020'],
  banner: { js: '/* mars-globe — 3D Mars globe for CesiumJS. Requires window.Cesium. MIT. */' },
  plugins: [cesiumGlobal],
  logLevel: 'info',
});
