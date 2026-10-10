import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Разработка: `python -m api --dev --port 8765` + `npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
})
