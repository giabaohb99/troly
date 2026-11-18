/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Trong container dev (docker-compose.dev.yml) api ở http://api:8000; chạy thẳng trên máy thì ở cổng 8200.
const apiTarget = process.env.API_PROXY_TARGET ?? (process.env.CHOKIDAR_USEPOLLING ? 'http://api:8000' : 'http://localhost:8200')

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // Tệp service worker của MSW chỉ phục vụ ở chế độ API giả, không vào bản build.
  publicDir: mode === 'mock' ? 'mock-public' : 'public',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5190,
    // Mã trên ổ Windows gắn vào container: dò định kỳ thay vì chờ sự kiện đổi tệp.
    watch: { usePolling: Boolean(process.env.CHOKIDAR_USEPOLLING) },
    proxy: { '/api': apiTarget },
  },
  build: { sourcemap: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    env: { TZ: 'Asia/Ho_Chi_Minh' },
  },
}))
