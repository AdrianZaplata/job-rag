// Phase 7 Plan 05 — route composition for /profile per CONTEXT.md D-28.
//
// Single React state machine owned by useResumeUpload:
//   - idle     → <ProfileView/> (current skills) + <ResumeUploader/> (upload affordance)
//   - reviewing → <ReviewPanel/> (status-pill diff chip list + sticky footer)
//   - saved    → same as idle (the hook flips back via reset() conceptually; we
//                immediately surface the refreshed ProfileView once cache hydrated)
//
// PATTERNS §24 / UI-SPEC §6a analog.

import { ProfileView } from '@/components/profile/ProfileView'
import { ResumeUploader } from '@/components/profile/ResumeUploader'
import { ReviewPanel } from '@/components/profile/ReviewPanel'
import { useResumeUpload } from '@/components/profile/useResumeUpload'
import type { DiffItemState } from '@/components/profile/types'

export function ProfilePage() {
  const { state, setState, upload, save, reset } = useResumeUpload()

  if (state.phase === 'reviewing') {
    return (
      <div className="mx-auto w-full max-w-3xl px-6 py-6 space-y-6">
        <h1 className="text-lg font-semibold">Profile</h1>
        <ReviewPanel
          diff={state.diff}
          extractionId={state.extractionId}
          onSave={(payload) => save.mutate(payload)}
          onCancel={reset}
          isSaving={save.isPending}
          setDiff={(diff: DiffItemState[]) =>
            setState({ ...state, diff })
          }
        />
      </div>
    )
  }

  // 'idle' and 'saved' both surface the ProfileView + ResumeUploader.
  // After a successful save the hook flips to 'saved'; the ['profile'] cache
  // was updated synchronously inside the save mutation's onSuccess so the
  // ProfileView re-renders with the new skill list immediately.
  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-6 space-y-6">
      <h1 className="text-lg font-semibold">Profile</h1>
      <ProfileView />
      <ResumeUploader
        onUpload={(file) => upload.mutate(file)}
        isPending={upload.isPending}
        isError={upload.isError}
        error={upload.error as Error | null}
      />
    </div>
  )
}
