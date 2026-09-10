import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento local o backend roda em localhost:8000.
// Dentro do docker-compose o proxy aponta para http://backend:8000
// (VITE_PROXY_TARGET é definido no compose).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})