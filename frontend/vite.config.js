import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:3000'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1', port: 5176, strictPort: true,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/socket.io': { target: backend, changeOrigin: true, ws: true }
    }
  }
})
