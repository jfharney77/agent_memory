import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // 5173 and 8000 are commonly taken by other projects on this machine,
    // so both ends of this app sit on their own ports and refuse to wander.
    port: 5180,
    strictPort: true,
    // The demos are Python. The backend runs them and streams stdout back.
    proxy: { '/api': { target: 'http://127.0.0.1:8077', changeOrigin: true } },
  },
})
