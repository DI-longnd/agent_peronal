import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev: proxy /api + /ws sang server FastAPI (port 8000) để `npm run dev` chạy
// không cần CORS. Prod: FastAPI serve thẳng web/dist — cùng origin, không proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
