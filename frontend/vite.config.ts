import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5140,
    allowedHosts: true,
    proxy: {
      '/ws': {
        target: 'http://backend:5141',
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
