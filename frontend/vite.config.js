import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Dev server port 5173 matches the backend CORS allow-list
// (http://localhost:5173 / http://127.0.0.1:5173).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    strictPort: true
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
})
