import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const API = process.env.CMD_API || 'http://127.0.0.1:8000';

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { '/api': API, '/oauth': API, '/mcp': API } },
}));
