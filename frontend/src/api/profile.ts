// Phase 7 (Profile + Resume) — typed service module per CONTEXT.md D-29 / PATTERNS §25.
// Three async functions wrap authedFetch and return the openapi-typescript-codegened
// response types. Consumes Plan 04 endpoints:
//
//   - GET   /profile          → UserSkillProfile
//   - POST  /profile/upload   → ResumeUploadResponse (multipart/form-data)
//   - PATCH /profile          → UserSkillProfile (None = no change semantics)
//
// Used by:
//   - useResumeUpload hook (upload + save mutations)
//   - ProfileView component (getProfile via TanStack Query key ['profile'])

import { authedFetch } from '@/api/authedFetch'
import type { components } from '@/api/types'

// Re-export codegen-derived types so downstream consumers import from here.
export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
export type UserProfileUpdate = components['schemas']['UserProfileUpdate']
export type UserSkillProfile = components['schemas']['UserSkillProfile']
export type SkillDiffItem = components['schemas']['SkillDiffItem']

/** GET /profile - returns the authenticated user's profile (PROF-01). */
export async function getProfile(signal?: AbortSignal): Promise<UserSkillProfile> {
  const res = await authedFetch('/profile', { signal })
  if (!res.ok) throw new Error(`profile: HTTP ${res.status}`)
  return res.json() as Promise<UserSkillProfile>
}

/** POST /profile/upload - multipart resume upload (PROF-02, PROF-04). */
export async function uploadResume(
  file: File,
  signal?: AbortSignal,
): Promise<ResumeUploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  // NOTE: do NOT set Content-Type for FormData — the browser sets
  // multipart/form-data; boundary=... automatically. Setting it manually
  // produces a malformed body without the boundary parameter.
  const res = await authedFetch('/profile/upload', {
    method: 'POST',
    body: fd,
    signal,
  })
  if (!res.ok) {
    // D-35 error taxonomy — backend returns { detail: { reason, message } }
    const err = await res.json().catch(() => ({}))
    const reason: string =
      err?.detail?.reason ?? err?.reason ?? `upload: HTTP ${res.status}`
    throw new Error(reason)
  }
  return res.json() as Promise<ResumeUploadResponse>
}

/** PATCH /profile - replaces skills_json; None = no change (PROF-06). */
export async function saveProfile(
  payload: UserProfileUpdate,
  signal?: AbortSignal,
): Promise<UserSkillProfile> {
  const res = await authedFetch('/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(`profile-save: HTTP ${res.status}`)
  return res.json() as Promise<UserSkillProfile>
}
