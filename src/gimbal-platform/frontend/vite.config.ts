import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    // LAN: bind on all interfaces so teammates can reach the dev server
    // via the host's LAN IP. Vite still proxies /api -> 127.0.0.1:8000
    // server-side, so the browser never has to know the backend address.
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE requires the upstream response to stream through
        // unbuffered.  Default Vite proxy buffers the response until
        // the upstream closes it; for SSE that defeats live tailing.
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes) => {
            // Strip upstream caching headers and tell nginx-style
            // reverse proxies not to buffer the body.
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
      // V3 composer 的接口目录 (Catalog Panel) 直接拉 Plate 的端点契约
      '/plate': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/plate/, ''),
      },
    }
  }
})
