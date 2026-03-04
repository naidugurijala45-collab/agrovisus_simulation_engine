import { defineConfig } from 'vite'

export default defineConfig({
    esbuild: {
        jsx: 'automatic',
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:8001',
                changeOrigin: true,
            },
        },
    },
    optimizeDeps: {
        include: ['react', 'react-dom', 'react-router-dom', 'recharts', 'axios'],
    },
})
