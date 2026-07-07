import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5401,
    proxy: {
      '/api': {
        target: 'http://localhost:5400',
        changeOrigin: true,
      },
    },
  },
})
