import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/landing/' : '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/media': 'http://127.0.0.1:5000',
      '/video_feed': 'http://127.0.0.1:5000',
    },
  },
  build: {
    outDir: 'static/landing',
    emptyOutDir: true,
    sourcemap: false,
  },
}))
