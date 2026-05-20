import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Vitest-specific config — kept separate from vite.config.ts to avoid the
// rolldown (Vite 8) vs rollup (vitest's bundled Vite) plugin-type collision.
// We DON'T include @tailwindcss/vite here because tests don't render real CSS
// (`css: false` below); skipping the plugin avoids touching the rolldown chain.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
  },
})
