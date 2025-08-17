import { defineConfig } from 'vite'
import path from 'path'
import react from '@vitejs/plugin-react-swc'

// 简化的配置用于测试
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  base: '/webui/',
  server: {
    proxy: {
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/query': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/documents': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})