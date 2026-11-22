import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Windows Docker bind mounts do not reliably emit file change events.
    watch: { usePolling: true, interval: 500 },
    proxy: { '/api': process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000' },
  },
})

