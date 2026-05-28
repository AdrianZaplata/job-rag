// Phase 7 Plan 05 — useResumeUpload hook tests per VALIDATION 07-05-09.
//
// Covers:
//   - upload mutation transitions idle → reviewing (with D-25 default tick states)
//   - save mutation invalidates ['profile'] AND ['dashboard'] cache keys (D-22)
//   - reset() returns to idle phase

import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'

import { useResumeUpload } from './useResumeUpload'

vi.mock('@/api/profile', () => ({
  uploadResume: vi.fn(),
  saveProfile: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { saveProfile, uploadResume } from '@/api/profile'
import { toast } from 'sonner'

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

function newQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

describe('useResumeUpload', () => {
  it('upload mutation transitions idle → reviewing with D-25 default tick states', async () => {
    vi.mocked(uploadResume).mockResolvedValueOnce({
      extracted: {
        skills: [],
        target_roles: [],
        preferred_locations: [],
        min_salary_eur: null,
        remote_preference: 'unknown',
        years_experience: null,
      },
      skills_diff: [
        { name: 'Rust', source: 'added', editable: true },
        { name: 'Docker', source: 'removed', editable: false },
        { name: 'Python', source: 'unchanged', editable: false },
      ],
      prompt_version: '1.0',
      extraction_id: '00000000-0000-0000-0000-000000000abc',
    })

    const qc = newQueryClient()
    const { result } = renderHook(() => useResumeUpload(), {
      wrapper: makeWrapper(qc),
    })

    expect(result.current.state.phase).toBe('idle')

    await act(async () => {
      await result.current.upload.mutateAsync(
        new File([new Uint8Array(1)], 'r.pdf'),
      )
    })

    await waitFor(() => expect(result.current.state.phase).toBe('reviewing'))

    if (result.current.state.phase !== 'reviewing') {
      throw new Error('expected reviewing phase')
    }

    expect(result.current.state.extractionId).toBe(
      '00000000-0000-0000-0000-000000000abc',
    )

    const byName = Object.fromEntries(
      result.current.state.diff.map((d) => [d.name, d]),
    )
    // D-25 default tick states
    expect(byName.Rust.checked).toBe(true) // added → checked
    expect(byName.Docker.checked).toBe(false) // removed → unchecked
    expect(byName.Python.checked).toBe(true) // unchanged → checked

    // editedName always initialised to name
    expect(byName.Rust.editedName).toBe('Rust')
    expect(byName.Docker.editedName).toBe('Docker')
    expect(byName.Python.editedName).toBe('Python')
  })

  it('save mutation invalidates [profile] AND [dashboard] cache keys (D-22)', async () => {
    // Seed: upload resolves first to put us in reviewing phase.
    vi.mocked(uploadResume).mockResolvedValueOnce({
      extracted: {
        skills: [],
        target_roles: [],
        preferred_locations: [],
        min_salary_eur: null,
        remote_preference: 'unknown',
        years_experience: null,
      },
      skills_diff: [{ name: 'Rust', source: 'added', editable: true }],
      prompt_version: '1.0',
      extraction_id: '00000000-0000-0000-0000-000000000abc',
    })

    const persisted = {
      skills: [{ name: 'Rust' }],
      target_roles: [],
      preferred_locations: [],
      min_salary: null,
      min_salary_eur: null,
      remote_preference: 'unknown' as const,
    }
    vi.mocked(saveProfile).mockResolvedValueOnce(persisted)

    const qc = newQueryClient()
    const setDataSpy = vi.spyOn(qc, 'setQueryData')
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useResumeUpload(), {
      wrapper: makeWrapper(qc),
    })

    await act(async () => {
      await result.current.upload.mutateAsync(
        new File([new Uint8Array(1)], 'r.pdf'),
      )
    })
    await waitFor(() => expect(result.current.state.phase).toBe('reviewing'))

    await act(async () => {
      await result.current.save.mutateAsync({
        skills: [{ name: 'Rust' }],
        target_roles: null,
        preferred_locations: null,
        min_salary_eur: null,
        remote_preference: null,
        extraction_id: '00000000-0000-0000-0000-000000000abc',
      })
    })

    // WR-05: `saved` is transient — the hook auto-reverts to `idle` on the
    // next macrotask. The user-visible contract from types.ts D-28 is
    // "saved → idle after Sonner toast + cache invalidation."
    await waitFor(() => expect(result.current.state.phase).toBe('idle'))

    // D-22 contract:
    expect(setDataSpy).toHaveBeenCalledWith(['profile'], persisted)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
    // WR-05: Sonner toast fired with skill-count.
    expect(toast.success).toHaveBeenCalledWith(
      'Saved 1 skills to your profile',
    )
  })

  it('reset() returns to idle phase from reviewing', async () => {
    vi.mocked(uploadResume).mockResolvedValueOnce({
      extracted: {
        skills: [],
        target_roles: [],
        preferred_locations: [],
        min_salary_eur: null,
        remote_preference: 'unknown',
        years_experience: null,
      },
      skills_diff: [{ name: 'Rust', source: 'added', editable: true }],
      prompt_version: '1.0',
      extraction_id: '00000000-0000-0000-0000-000000000abc',
    })

    const qc = newQueryClient()
    const { result } = renderHook(() => useResumeUpload(), {
      wrapper: makeWrapper(qc),
    })

    await act(async () => {
      await result.current.upload.mutateAsync(
        new File([new Uint8Array(1)], 'r.pdf'),
      )
    })
    await waitFor(() => expect(result.current.state.phase).toBe('reviewing'))

    act(() => {
      result.current.reset()
    })

    expect(result.current.state.phase).toBe('idle')
  })
})
