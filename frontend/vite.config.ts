/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';

const cesiumSource = 'node_modules/cesium/Build/Cesium';
// Cesium needs its static assets served under a known base URL (CESIUM_BASE_URL).
// We copy them to dist/cesium and point window.CESIUM_BASE_URL at '/cesium' in main.tsx.
const cesiumAssets = ['Workers', 'ThirdParty', 'Assets', 'Widgets'];

// DEV ONLY: serve /cesium/* directly from the installed Cesium package. In the dev
// server, vite-plugin-static-copy populates the BUILD output but does not serve these
// paths, so Cesium's fetch of e.g. Assets/approximateTerrainHeights.json would hit the
// SPA fallback (index.html) and crash on JSON.parse. This middleware returns the real
// file with a correct content-type before the fallback runs.
function serveCesiumAssetsInDev() {
  const root = path.resolve(cesiumSource);
  const mimes: Record<string, string> = {
    '.js': 'text/javascript',
    '.cjs': 'text/javascript',
    '.mjs': 'text/javascript',
    '.json': 'application/json',
    '.wasm': 'application/wasm',
    '.css': 'text/css',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.xml': 'application/xml',
    '.glb': 'model/gltf-binary',
    '.ktx2': 'image/ktx2',
  };
  return {
    name: 'serve-cesium-assets-dev',
    apply: 'serve' as const,
    configureServer(server: {
      middlewares: {
        use: (fn: (req: IncomingMessage, res: ServerResponse, next: () => void) => void) => void;
      };
    }) {
      server.middlewares.use((req, res, next) => {
        const url: string = req.url || '';
        if (!url.startsWith('/cesium/')) return next();
        const rel = decodeURIComponent(url.split('?')[0].replace(/^\/cesium\//, ''));
        const fp = path.resolve(root, rel);
        if (!fp.startsWith(root) || !fs.existsSync(fp) || !fs.statSync(fp).isFile()) return next();
        res.setHeader('Content-Type', mimes[path.extname(fp).toLowerCase()] || 'application/octet-stream');
        fs.createReadStream(fp).pipe(res);
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_URL && env.VITE_API_URL.startsWith('http') ? env.VITE_API_URL : 'http://localhost:8000';

  return {
    base: './',
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
      // Cesium must resolve to a single copy or its module-level singletons (Ellipsoid.default) break.
      dedupe: ['cesium'],
    },
    define: {
      // Build-time fallback; main.tsx still sets window.CESIUM_BASE_URL at runtime.
      CESIUM_BASE_URL: JSON.stringify('/cesium'),
    },
    plugins: [
      serveCesiumAssetsInDev(),
      react(),
      viteStaticCopy({
        targets: cesiumAssets.map((dir) => ({
          src: path.posix.join(cesiumSource, dir),
          dest: 'cesium',
        })),
      }),
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/openapi.json': { target: apiTarget, changeOrigin: true },
        // Optional CORS fallback for Trek basemap tiles (enable with VITE_TREK_VIA_PROXY=true).
        '/trek': {
          target: 'https://trek.nasa.gov',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/trek/, ''),
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 4000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/cesium')) return 'cesium';
            return undefined;
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['src/test/setup.ts'],
      css: false,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  };
});
