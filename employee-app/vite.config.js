import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: process.env.EMPLOYEE_NATIVE_BUILD === '1' ? './' : '/employee/',
  server: {
    proxy: { '/api': { target: process.env.EMPLOYEE_DEV_API_ORIGIN || 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
