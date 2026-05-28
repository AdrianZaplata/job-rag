// Phase 7 Plan 05 — TanStack mutation state-machine hook per CONTEXT.md D-29 + RESEARCH §11.
//
// Owns: the upload mutation, the save mutation, the review-phase state machine,
// and the post-save TanStack cache invalidation contract (D-22).
//
// State transitions:
//   idle ── uploadResume success ──► reviewing (diff hydrated; extractionId captured)
//   reviewing ── saveProfile success ──► saved (toast + cache invalidate)
//   saved / reviewing ── reset() ──► idle
//
// Cache invalidation per D-22:
//   - setQueryData(['profile'], persistedProfile) — hydrate from the PATCH response
//   - invalidateQueries(['dashboard'])           — Phase 5 CV-vs-market re-fetches
//                                                  with the new skills counted

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { saveProfile, uploadResume } from '@/api/profile'
import type { UserProfileUpdate } from '@/api/profile'

import type { DiffItemState, ReviewState } from './types'

export function useResumeUpload() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<ReviewState>({ phase: 'idle' })

  const upload = useMutation({
    mutationFn: (file: File) => uploadResume(file),
    onSuccess: (resp) => {
      // D-25 default tick states: added✓ / removed☐ / unchanged✓
      // editedName starts as a copy of name; user rewrites via Pencil on added rows only (D-26).
      const diff: DiffItemState[] = resp.skills_diff.map((d) => ({
        ...d,
        checked: d.source !== 'removed',
        editedName: d.name,
      }))
      setState({
        phase: 'reviewing',
        diff,
        extractionId: resp.extraction_id,
      })
    },
  })

  const save = useMutation({
    mutationFn: (payload: UserProfileUpdate) => saveProfile(payload),
    onSuccess: (profile) => {
      // D-22: hydrate ['profile'] from the PATCH response + invalidate the
      // ['dashboard'] family so Phase 5's CV-vs-market widget re-fetches with
      // the new skill set counted.
      queryClient.setQueryData(['profile'], profile)
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      // WR-05: surface the success via the AppShell-mounted Sonner Toaster
      // (the types.ts D-28 comment promises this) and flip to the transient
      // `saved` phase. `saved` is observable for one microtask before the
      // auto-revert; the ProfileView + ResumeUploader render the same in
      // both saved + idle, so the user sees the refreshed profile via the
      // synchronous setQueryData above.
      setState({ phase: 'saved' })
      toast.success(`Saved ${profile.skills.length} skills to your profile`)
      // Auto-revert so `saved` is genuinely transient (matches types.ts D-28).
      setTimeout(() => setState({ phase: 'idle' }), 0)
    },
  })

  const reset = () => setState({ phase: 'idle' })

  return { state, setState, upload, save, reset }
}
