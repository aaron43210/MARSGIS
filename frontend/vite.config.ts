/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const cesiumSource = 'node_modules/cesium/Build/Cesium';
// Cesium needs its static assets served under a known base URL (CESIUM_BASE_URL).
// We copy them to dist/cesium and point window.CESIUM_BASE_URL at '/cesium' in main.tsx.
const cesiumAssets = ['Workers', 'ThirdParty', 'Assets', 'Widgets'];

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
