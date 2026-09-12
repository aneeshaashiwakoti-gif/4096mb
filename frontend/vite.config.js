import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/impact': 'http://127.0.0.1:8000',
      '/ask': 'http://127.0.0.1:8000',
      '/fix': 'http://127.0.0.1:8000',
      '/validate': 'http://127.0.0.1:8000',
    },
  },
});
