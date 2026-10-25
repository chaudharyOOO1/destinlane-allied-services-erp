import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: process.env.EMPLOYEE_NATIVE_BUILD === '1' ? './' : '/employee/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
