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
    environmentOptions: {
      jsdom: {
        // Non-opaque origin so jsdom's localStorage is actually available.
        // Without this, Node's experimental global localStorage takes over and
        // is missing .clear() / .getItem() under the `--localstorage-file`
        // warning (Node 22+ ships a different impl).
        url: 'http://localhost/',
      },
    },
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
  },
})
