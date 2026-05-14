import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react-router')) return 'vendor-react';
            if (id.includes('react-dom') || id.includes('/react/')) return 'vendor-react';
            if (id.includes('@reduxjs') || id.includes('react-redux')) return 'vendor-redux';
            if (id.includes('recharts')) return 'vendor-charts';
            if (id.includes('framer-motion')) return 'vendor-motion';
          }
        },
      },
    },
  },
})
