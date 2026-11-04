import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Run the backend with: uvicorn app.main:app --app-dir src/backend
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
