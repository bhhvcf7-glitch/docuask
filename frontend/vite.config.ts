import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/documents': 'http://127.0.0.1:8000',
      '/search': 'http://127.0.0.1:8000',
      '/qa': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
  test: { environment: 'node' },
})
