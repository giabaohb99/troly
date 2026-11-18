// Khung tối thiểu (việc 0-06). Agent app Android thay theo docs/30-app.
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5190,
    // Mã trên ổ Windows gắn vào container: dò định kỳ thay vì chờ sự kiện đổi tệp.
    watch: { usePolling: true },
    proxy: { '/api': 'http://api:8000' },
  },
})
