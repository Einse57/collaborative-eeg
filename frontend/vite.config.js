import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // Listen on all network interfaces for remote access
    port: 3000,
    // Proxy removed - frontend will connect directly to backend via VITE_API_URL
  }
})
