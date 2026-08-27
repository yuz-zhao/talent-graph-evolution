import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // 依赖预构建只扫描真实入口 index.html，避免把 crawler/data 下 383 个
  // 抓取网页 HTML 当成入口解析其外部 <script src>，导致首次加载卡十几秒
  optimizeDeps: {
    entries: ['index.html'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        // Development UI uses the Docker API published by .env.docker.
        // Override when intentionally running a different backend.
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
    },
  },
  build: {
    commonjsOptions: {
      transformMixedEsModules: true,
    }
  }
})
