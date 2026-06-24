// Phase 7 Plan 05 — local feature types for the profile/resume-upload review UI.
// CONTEXT.md D-29 verbatim component-tree entry.
//
// `DiffItemState` extends the codegen `SkillDiffItem` with per-row UI draft state:
//   - `checked`: tick state per D-25 defaults (added✓ / removed☐ / unchanged✓)
//   - `editedName`: user-renamed value (only ever set when source==='added' per D-26)
//
// `ReviewState` is the hook's phase-machine union per D-28 (idle / reviewing / saved).

import type { components } from '@/api/types'

export type SkillDiffItem = components['schemas']['SkillDiffItem']
export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
export type UserProfileUpdate = components['schemas']['UserProfileUpdate']
export type UserSkillProfile = components['schemas']['UserSkillProfile']

/**
 * Per-row UI draft state for the diff review.
 *
 * D-25 default tick states (set when the upload response is loaded):
 *   - source==='added'     → checked: true   (trust extraction by default)
 *   - source==='removed'   → checked: false  (do NOT keep removed unless ticked)
 *   - source==='unchanged' → checked: true   (existing skills stay)
 *
 * D-26 rename scope (locked):
 *   - source==='added'     → editable (Pencil affordance + inline Input)
 *   - source==='removed'   → read-only name
 *   - source==='unchanged' → read-only name
 *
 * `editedName` always carries the current display name (initialised to `name`
 * on load). When source==='added' AND the user renames via the Pencil affordance,
 * `editedName` diverges from `name`; the save payload uses `editedName`.
 */
export type DiffItemState = SkillDiffItem & {
  checked: boolean
  editedName: string
}

/**
 * Hook-owned phase machine per D-28.
 *
 *   idle      → renders <ProfileView/> + <ResumeUploader/>
 *   reviewing → renders <ReviewPanel/> (diff loaded; user editing draft)
 *   saved     → transient — flips back to `idle` after Sonner toast + cache invalidation.
 *
 * `extractionId` (UUID) travels from the upload response into the PATCH payload
 * so Langfuse correlates the `profile_save` span to the same trace per D-32.
 */
export type ReviewState =
  | { phase: 'idle' }
  | { phase: 'reviewing'; diff: DiffItemState[]; extractionId: string }
  | { phase: 'saved' }
