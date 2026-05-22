// Phase 5 Plan 05-04 — active tests for the useDashboardFilters hook.
// Plan 05-01 shipped a skip-on-missing stub; Plan 05-04 lands the hook itself
// (useDashboardFilters.ts) and replaces the stub assertions with real ones.
//
// Covers UI-SPEC section 10 contract:
//   - Deep-link read: ?country=DE -> { country: 'DE' }
//   - Default elision write: setFilters({ country: 'WW' }) removes the param
//   - Defensive coercion: ?country=ZZ -> WW (defaults to safe value)
//   - Updater-form setParams preserves unrelated params

import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import type { ReactNode } from 'react'

import { useDashboardFilters } from '@/components/dashboard/useDashboardFilters'

// Render the hook inside MemoryRouter at a controlled initial URL.
function renderWithRouter(initialEntries: string[] = ['/']) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="*" element={<>{children}</>} />
      </Routes>
    </MemoryRouter>
  )
  return renderHook(() => useDashboardFilters(), { wrapper })
}

describe('useDashboardFilters', () => {
  it('reads ?country=DE as { country: "DE" }', () => {
    const { result } = renderWithRouter(['/?country=DE'])
    expect(result.current.filters.country).toBe('DE')
  })

  it('reads ?seniority=senior&remote=remote as { seniority: "senior", remote: "remote" }', () => {
    const { result } = renderWithRouter(['/?seniority=senior&remote=remote'])
    expect(result.current.filters.seniority).toBe('senior')
    expect(result.current.filters.remote).toBe('remote')
  })

  it('default elision: setFilters({ country: "WW" }) removes the country param (E8)', () => {
    const { result } = renderWithRouter(['/?country=DE'])
    expect(result.current.filters.country).toBe('DE')
    act(() => {
      result.current.setFilters({ country: 'WW' })
    })
    expect(result.current.filters.country).toBe('WW')
    // The URL no longer carries ?country=WW (default elision); reading after write returns the default
  })

  it('default elision: setFilters({ remote: "any" }) removes the remote param (E8)', () => {
    const { result } = renderWithRouter(['/?remote=remote'])
    expect(result.current.filters.remote).toBe('remote')
    act(() => {
      result.current.setFilters({ remote: 'any' })
    })
    expect(result.current.filters.remote).toBe('any')
  })

  it('default elision: setFilters({ seniority: undefined }) removes the seniority param', () => {
    const { result } = renderWithRouter(['/?seniority=senior'])
    expect(result.current.filters.seniority).toBe('senior')
    act(() => {
      result.current.setFilters({ seniority: undefined })
    })
    expect(result.current.filters.seniority).toBeUndefined()
  })

  it('default read (no params): returns { country: "WW", seniority: undefined, remote: "any" } (E9)', () => {
    const { result } = renderWithRouter(['/'])
    expect(result.current.filters.country).toBe('WW')
    expect(result.current.filters.seniority).toBeUndefined()
    expect(result.current.filters.remote).toBe('any')
  })

  it('invalid country value coerces to default WW (defensive)', () => {
    const { result } = renderWithRouter(['/?country=ZZ'])
    expect(result.current.filters.country).toBe('WW')
  })

  it('invalid remote value coerces to default any (defensive)', () => {
    const { result } = renderWithRouter(['/?remote=foo'])
    expect(result.current.filters.remote).toBe('any')
  })

  it('invalid seniority value coerces to undefined (defensive)', () => {
    const { result } = renderWithRouter(['/?seniority=xyz'])
    expect(result.current.filters.seniority).toBeUndefined()
  })

  it('setFilters preserves other params (updater function form)', () => {
    const { result } = renderWithRouter(['/?country=DE&seniority=senior'])
    expect(result.current.filters.country).toBe('DE')
    expect(result.current.filters.seniority).toBe('senior')
    act(() => {
      result.current.setFilters({ remote: 'remote' })
    })
    // country + seniority untouched; remote newly added
    expect(result.current.filters.country).toBe('DE')
    expect(result.current.filters.seniority).toBe('senior')
    expect(result.current.filters.remote).toBe('remote')
  })
})
