import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
  },
  // plotly.js's dependency chain references the Node global `global`,
  // which doesn't exist in the browser — without this the app throws
  // "global is not defined" before it can even mount.
  define: {
    global: 'globalThis',
  },
})
