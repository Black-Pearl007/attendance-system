import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the React dev server (5173) proxies /api to FastAPI (8000),
// so the browser sees a single origin and no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
