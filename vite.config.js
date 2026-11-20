import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import cesium from 'vite-plugin-cesium';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react(), cesium()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: p => p.replace(/^\/api/, '') } },
  },
  build: { chunkSizeWarningLimit: 1500, rollupOptions: { input: {
    index: fileURLToPath(new URL('./index.html', import.meta.url)),
    console: fileURLToPath(new URL('./console.html', import.meta.url)),
  } } },
});
