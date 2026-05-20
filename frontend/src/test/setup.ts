import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

// jsdom doesn't implement window.matchMedia. Sonner (via next-themes) and
// ThemeToggle both consume it; supply a deterministic stub so components that
// query OS theme preference don't blow up under tests.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(), // legacy
      removeListener: vi.fn(), // legacy
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

// Node 22+ ships an experimental global `localStorage` (gated by --localstorage-file).
// On Node 25 it leaks into the jsdom environment and shadows jsdom's per-window
// implementation, returning an object that's missing the standard Storage methods
// (getItem / setItem / removeItem / clear / key / length). Reinstall an in-memory
// Storage-compatible shim on the jsdom window so test code sees the expected shape.
function installLocalStorageShim() {
  const store = new Map<string, string>()
  const shim: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? (store.get(key) as string) : null
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    },
  }
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    writable: true,
    value: shim,
  })
  // Also patch the global so `localStorage.xxx` (bare) resolves to the shim.
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    writable: true,
    value: shim,
  })
}

installLocalStorageShim()

beforeEach(() => {
  // Fresh storage per test (avoids cross-test pollution without forcing every
  // test to call window.localStorage.clear() in its own beforeEach).
  installLocalStorageShim()
})

afterEach(() => {
  cleanup()
})
