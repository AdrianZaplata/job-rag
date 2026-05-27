---
phase: 07-profile-resume-upload
plan: 05
type: execute
wave: 3
depends_on: [04]
files_modified:
  - frontend/src/api/profile.ts
  - frontend/src/components/profile/types.ts
  - frontend/src/components/profile/ProfileView.tsx
  - frontend/src/components/profile/ResumeUploader.tsx
  - frontend/src/components/profile/SkillDiffChip.tsx
  - frontend/src/components/profile/ReviewPanel.tsx
  - frontend/src/components/profile/useResumeUpload.ts
  - frontend/src/components/profile/ProfileView.test.tsx
  - frontend/src/components/profile/ResumeUploader.test.tsx
  - frontend/src/components/profile/SkillDiffChip.test.tsx
  - frontend/src/components/profile/ReviewPanel.test.tsx
  - frontend/src/components/profile/useResumeUpload.test.tsx
  - frontend/src/routes/Profile.tsx
autonomous: true
requirements: [PROF-05]
requirements_addressed: [PROF-05, PROF-06]

must_haves:
  truths:
    - "frontend/src/components/profile/ directory contains 6 source files + 5 test files per D-29"
    - "ProfileView renders read-only Badge chips of current skills with count in header"
    - "ResumeUploader accepts PDF/DOCX via input + drag-drop; client-side pre-checks size <=2 MB and extension"
    - "ResumeUploader shows stepped cold-start copy (Reading, Asking the agent, Still working) per D-31"
    - "SkillDiffChip shows green pill for added, red for removed, muted for unchanged per D-24"
    - "SkillDiffChip on added items shows Pencil icon; click enters inline-edit; Enter saves, Esc cancels per D-26"
    - "ReviewPanel shows sticky footer with live summary 'Save profile (N skills)' updated on tick"
    - "useResumeUpload state machine transitions idle -> reviewing -> saved"
    - "Save mutation invalidates ['profile'] AND ['dashboard'] query keys per D-22"
    - "Profile.tsx no longer renders PhasePlaceholder; uses ProfileView / ReviewPanel conditional"
  artifacts:
    - path: "frontend/src/api/profile.ts"
      provides: "getProfile, uploadResume, saveProfile typed service functions"
      contains: "uploadResume"
    - path: "frontend/src/components/profile/types.ts"
      provides: "DiffItemState type extending codegen SkillDiffItem"
      contains: "DiffItemState"
    - path: "frontend/src/components/profile/ProfileView.tsx"
      provides: "Read-only current skills surface"
    - path: "frontend/src/components/profile/ResumeUploader.tsx"
      provides: "File input + drag-drop + cold-start stepped status"
    - path: "frontend/src/components/profile/SkillDiffChip.tsx"
      provides: "Chip atom with status pill + tick + inline edit"
    - path: "frontend/src/components/profile/ReviewPanel.tsx"
      provides: "Card composing chip list + sticky footer save UI"
    - path: "frontend/src/components/profile/useResumeUpload.ts"
      provides: "TanStack mutation state machine hook"
    - path: "frontend/src/routes/Profile.tsx"
      provides: "Page composition: idle ProfileView+Uploader / reviewing ReviewPanel"
  key_links:
    - from: "frontend/src/routes/Profile.tsx"
      to: "useResumeUpload"
      via: "import + invoke + conditional render"
      pattern: "useResumeUpload"
    - from: "frontend/src/api/profile.ts"
      to: "authedFetch"
      via: "GET / POST FormData / PATCH JSON against /profile* (all backed by Plan 04)"
      pattern: "authedFetch.*profile"
    - from: "useResumeUpload save mutation"
      to: "queryClient.invalidateQueries"
      via: "Phase 5 dashboard cache propagation"
      pattern: "invalidateQueries.*dashboard"
---

<objective>
Ship the Phase 7 frontend feature folder: 6 source files + 5 vitest+RTL tests under `frontend/src/components/profile/`, fill the `frontend/src/api/profile.ts` stub with three typed service functions, and replace the `PhasePlaceholder` in `frontend/src/routes/Profile.tsx` with the real two-state page. This closes PROF-05 (review panel UI) and the frontend half of PROF-06 (save flow + dashboard cache invalidation).

Purpose: After Plan 04 lands the backend (POST /profile/upload + PATCH /profile + GET /profile) + OpenAPI snapshot, the frontend can codegen against `ResumeUploadResponse`, `UserProfileUpdate`, `SkillDiffItem`, and `UserSkillProfile` types AND consume the now-existing GET /profile endpoint via `getProfile()`. The feature folder mirrors Phase 5 (`components/dashboard/`) and Phase 6 (`components/chat/`) — one feature-owner hook + one page composition + atomic chip primitives + read-only view + uploader + review panel. The status-pill review panel (D-24) + inline-edit on added chips (D-26) + Langfuse-correlated save (D-29 `extraction_id`) together embody the "inspectable AI extraction" portfolio anchor from PROJECT.md Key Decisions.

**Scope discipline (CHECKER-FIX-1):** This plan is FRONTEND-ONLY. All backend routes (POST /profile/upload, PATCH /profile, GET /profile), the OpenAPI snapshot, and `tests/test_api.py` are already shipped by Plan 04 (Task 3 added GET /profile + the test_api.py append; Task 4 regenerated the snapshot). This plan only CONSUMES those artifacts via codegen types + `getProfile()` HTTP call. `files_modified` lists frontend files exclusively.

Output: 13 frontend files + Profile.tsx rewrite.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-RESEARCH.md
@.planning/phases/07-profile-resume-upload/07-PATTERNS.md
@.planning/phases/07-profile-resume-upload/07-VALIDATION.md
@.planning/phases/07-profile-resume-upload/07-UI-SPEC.md
@frontend/src/api/authedFetch.ts
@frontend/src/api/jobs.ts
@frontend/src/api/profile.ts
@frontend/src/api/types.ts
@frontend/src/components/dashboard/TopSkillsCard.tsx
@frontend/src/components/dashboard/useDashboardFilters.ts
@frontend/src/components/chat/useChatStream.ts
@frontend/src/components/chat/ChatComposer.tsx
@frontend/src/routes/Profile.tsx
@frontend/src/components/EmptyState.tsx

<interfaces>
Codegen types (from Plan 04 OpenAPI regen — `frontend/src/api/types.ts`):

    type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
        // { extracted, skills_diff, prompt_version, extraction_id }
    type SkillDiffItem = components['schemas']['SkillDiffItem']
        // { name, source: 'added' | 'removed' | 'unchanged', editable: boolean }
    type UserProfileUpdate = components['schemas']['UserProfileUpdate']
        // { skills, target_roles?, preferred_locations?, min_salary_eur?, remote_preference?, extraction_id? }
    type UserSkillProfile = components['schemas']['UserSkillProfile']
        // { skills, target_roles, preferred_locations, min_salary, remote_preference }

Backend routes shipped by Plan 04 — this plan ONLY consumes them:
- `GET /profile` → returns `UserSkillProfile` (Plan 04 Task 3 Step B)
- `POST /profile/upload` → returns `ResumeUploadResponse` (Plan 04 Task 2)
- `PATCH /profile` → returns `UserSkillProfile` (Plan 04 Task 3 Step A)

Existing primitives (no new shadcn installs needed):
- `frontend/src/components/ui/{card,button,badge,input,skeleton,alert,sonner}.tsx`
- `lucide-react` icons: `Pencil`, `Upload`, `FileText`, `X`, `Check`, `AlertCircle`

Phase 4 D-13 wrapper:

    import { authedFetch } from '@/api/authedFetch'
    // Supports FormData body (no manual Content-Type — browser sets multipart/form-data)
    // Returns standard Response; .ok / .json() / .status as usual

Phase 5 cache key pattern:

    queryKey: ['profile']                          // current profile (single source)
    queryClient.setQueryData(['profile'], profile) // hydrate from save response (D-22)
    queryClient.invalidateQueries({ queryKey: ['dashboard'] }) // Phase 5 cv-vs-market re-fetch

State machine (RESEARCH §11 lines 470-499):

    type ReviewState =
      | { phase: 'idle' }
      | { phase: 'reviewing'; diff: DiffItemState[]; extractionId: string }
      | { phase: 'saved' }

    type DiffItemState = SkillDiffItem & { checked: boolean; editedName: string }

Default tick states (D-25):
- added  -> checked: true
- removed -> checked: false  (i.e. "discard this removal" defaults to off — user TICKS to keep removed skill)
- unchanged -> checked: true

Save payload computation (D-21):
- final skill list = `diff.filter(d => d.checked).map(d => ({ name: d.editedName }))`
- target_roles / preferred_locations / min_salary_eur / remote_preference: pass `null` (v1 review panel only edits skills per D-Discretion)
- include `extraction_id` for Langfuse correlation (D-29)
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser file picker → API | Untrusted file bytes are subject to backend size/type gates; client-side pre-check is a UX nicety, not a security control |
| user-edited skill names in chip → PATCH body | Only the user's own profile is mutable (Adrian's oid is the only allowed user per AUTH-06); name strings reach DB after Pydantic validation |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-02 | Denial of Service (client pre-check) | ResumeUploader | mitigate | Client-side rejects >2 MB and non-{.pdf,.docx} extensions BEFORE the upload POST fires (D-30) — saves a network round-trip + a backend 413/415. Backend middleware is the authoritative backstop. Validated by `ResumeUploader.test.tsx` size + extension pre-check cases (VALIDATION 07-05-06). |
| T-07-05 | Spoofing (client pre-check) | ResumeUploader | mitigate | Client `accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"` + post-pick extension check. Backend D-08 + 415 backstop is the canonical gate. |
| T-07-foundation-XSS | Information disclosure | SkillDiffChip inline edit | accept | Skill names are rendered as text content, never as `dangerouslySetInnerHTML`. React's default text escaping is the mitigation. No additional sanitization needed. |
</threat_model>

<tasks>

<task type="auto" id="07-05-01">
  <name>Task 1: api/profile.ts service module + types.ts + useResumeUpload hook + hook tests</name>
  <files>frontend/src/api/profile.ts, frontend/src/components/profile/types.ts, frontend/src/components/profile/useResumeUpload.ts, frontend/src/components/profile/useResumeUpload.test.tsx</files>
  <read_first>
    - frontend/src/api/profile.ts (existing stub — confirm shape)
    - frontend/src/api/jobs.ts (analog: typed service module pattern — lines 1-67)
    - frontend/src/api/authedFetch.ts (confirms FormData and JSON body support)
    - frontend/src/api/types.ts (post-Plan-04 regen — verify ResumeUploadResponse / UserProfileUpdate / SkillDiffItem / UserSkillProfile exist AND GET /profile path is in the schema)
    - frontend/src/components/dashboard/useDashboardFilters.ts (re-export pattern lines 13-26)
    - frontend/src/components/dashboard/useDashboardFilters.test.tsx (existing hook test analog)
    - frontend/src/components/chat/useChatStream.ts (state-owner hook pattern lines 127-280; cleanup-on-unmount)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §21 (useResumeUpload analog lines 845-906)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §22 (types.ts analog lines 910-944)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §25 (profile.ts service analog lines 998-1052)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §11 (useResumeUpload state machine lines 470-505)
  </read_first>
  <action>
**Step A — Fill `frontend/src/api/profile.ts`** per PATTERNS §25. This plan ONLY consumes endpoints already shipped by Plan 04. The GET /profile, POST /profile/upload, and PATCH /profile handlers all exist in `src/job_rag/api/routes.py` and are reflected in the regenerated `frontend/src/api/types.ts`. No backend changes, no OpenAPI regen, no test_api.py append in this plan — that work is done.

Module body:

    import { authedFetch } from '@/api/authedFetch'
    import type { components } from '@/api/types'

    export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
    export type UserProfileUpdate = components['schemas']['UserProfileUpdate']
    export type UserSkillProfile = components['schemas']['UserSkillProfile']

    export async function getProfile(signal?: AbortSignal): Promise<UserSkillProfile> {
      const res = await authedFetch('/profile', { signal })
      if (!res.ok) throw new Error(`profile: HTTP ${res.status}`)
      return res.json() as Promise<UserSkillProfile>
    }

    export async function uploadResume(
      file: File,
      signal?: AbortSignal,
    ): Promise<ResumeUploadResponse> {
      const fd = new FormData()
      fd.append('file', file)
      const res = await authedFetch('/profile/upload', {
        method: 'POST',
        body: fd,
        signal,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const reason: string = err?.detail?.reason ?? `upload: HTTP ${res.status}`
        throw new Error(reason)
      }
      return res.json() as Promise<ResumeUploadResponse>
    }

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

NOTE: do NOT manually set Content-Type for the FormData POST — browser sets `multipart/form-data; boundary=...` automatically.

If `frontend/src/api/types.ts` does NOT contain a `/profile` path entry or the GET method on it, that indicates a Plan 04 regression — STOP and surface the gap before continuing. Plan 04 Task 4 Step B is responsible for committing the regenerated snapshot + types.ts including the GET /profile endpoint; this plan ASSUMES that work landed cleanly.

**Step B — Create `frontend/src/components/profile/types.ts`** per PATTERNS §22:

    import type { components } from '@/api/types'

    export type SkillDiffItem = components['schemas']['SkillDiffItem']
    export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
    export type UserProfileUpdate = components['schemas']['UserProfileUpdate']

    export type DiffItemState = SkillDiffItem & {
      checked: boolean
      editedName: string
    }

    export type ReviewState =
      | { phase: 'idle' }
      | { phase: 'reviewing'; diff: DiffItemState[]; extractionId: string }
      | { phase: 'saved' }

**Step C — Create `frontend/src/components/profile/useResumeUpload.ts`** per RESEARCH §11:

    import { useState } from 'react'
    import { useMutation, useQueryClient } from '@tanstack/react-query'
    import { saveProfile, uploadResume } from '@/api/profile'
    import type { UserProfileUpdate } from '@/api/profile'
    import type { DiffItemState, ReviewState } from './types'

    export function useResumeUpload() {
      const queryClient = useQueryClient()
      const [state, setState] = useState<ReviewState>({ phase: 'idle' })

      const upload = useMutation({
        mutationFn: (file: File) => uploadResume(file),
        onSuccess: (resp) => {
          const diff: DiffItemState[] = resp.skills_diff.map((d) => ({
            ...d,
            // D-25 default tick states
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
          // D-22: hydrate cache + invalidate dashboard for cv-vs-market refresh
          queryClient.setQueryData(['profile'], profile)
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          setState({ phase: 'saved' })
        },
      })

      const reset = () => setState({ phase: 'idle' })

      return { state, setState, upload, save, reset }
    }

**Step D — Create `frontend/src/components/profile/useResumeUpload.test.tsx`:**

Mirror the existing `useDashboardFilters.test.tsx` setup (QueryClientProvider wrapper). Required test cases per VALIDATION 07-05-09:

- `test('upload mutation transitions idle -> reviewing')`: mock `uploadResume` to resolve with `{ skills_diff: [...], extraction_id: 'abc' }`; render hook; call `upload.mutate(file)`; await mutation; assert `state.phase === 'reviewing'`; assert `state.diff` shape; assert default tick states (added/unchanged checked, removed unchecked)
- `test('save mutation invalidates [profile] and [dashboard]')`: mock `saveProfile` to resolve with a `UserSkillProfile`; spy on `queryClient.setQueryData` + `queryClient.invalidateQueries`; call `save.mutate(payload)`; await; assert `setQueryData` called with `['profile']`; assert `invalidateQueries` called with `{ queryKey: ['dashboard'] }`; assert `state.phase === 'saved'`
- `test('reset returns to idle')`: after a successful upload that transitions to reviewing, call `reset()`; assert `state.phase === 'idle'`

Use vitest `vi.mock('@/api/profile', ...)`. For the QueryClient spy, create a real QueryClient and spy on its methods via `vi.spyOn(queryClient, 'invalidateQueries')`.

Skeleton:

    import { describe, expect, it, vi } from 'vitest'
    import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
    import { act, renderHook, waitFor } from '@testing-library/react'
    import { useResumeUpload } from './useResumeUpload'

    vi.mock('@/api/profile', () => ({
      uploadResume: vi.fn(),
      saveProfile: vi.fn(),
    }))

    function wrapper(client: QueryClient) {
      return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={client}>{children}</QueryClientProvider>
      }
    }

    describe('useResumeUpload', () => {
      it('upload mutation transitions idle -> reviewing', async () => {
        const { uploadResume } = await import('@/api/profile')
        ;(uploadResume as any).mockResolvedValueOnce({
          extracted: { skills: [], target_roles: [], preferred_locations: [],
                       min_salary_eur: null, remote_preference: 'unknown',
                       years_experience: null },
          skills_diff: [
            { name: 'Rust', source: 'added', editable: true },
            { name: 'Docker', source: 'removed', editable: false },
            { name: 'Python', source: 'unchanged', editable: false },
          ],
          prompt_version: '1.0',
          extraction_id: '00000000-0000-0000-0000-000000000abc',
        })

        const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
        const { result } = renderHook(() => useResumeUpload(), { wrapper: wrapper(qc) })

        await act(async () => {
          await result.current.upload.mutateAsync(new File([new Uint8Array(1)], 'r.pdf'))
        })

        await waitFor(() => expect(result.current.state.phase).toBe('reviewing'))
        if (result.current.state.phase === 'reviewing') {
          const byName = Object.fromEntries(result.current.state.diff.map(d => [d.name, d]))
          expect(byName.Rust.checked).toBe(true)
          expect(byName.Docker.checked).toBe(false)
          expect(byName.Python.checked).toBe(true)
          expect(result.current.state.extractionId).toBe('00000000-0000-0000-0000-000000000abc')
        }
      })

      // ... save invalidation + reset tests
    })

Run:

    cd frontend && npm test -- --run useResumeUpload
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; npm run typecheck &amp;&amp; npm test -- --run useResumeUpload &amp;&amp; grep -E "export.*(uploadResume|saveProfile|getProfile)" src/api/profile.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -E "export.*(uploadResume|saveProfile)" frontend/src/api/profile.ts` returns the export lines (VALIDATION 07-05-03)
    - `grep -E "export.*getProfile" frontend/src/api/profile.ts` returns the getProfile export line
    - `frontend/src/components/profile/types.ts` exports `DiffItemState`, `ReviewState`, codegen re-exports
    - `frontend/src/components/profile/useResumeUpload.ts` exports `useResumeUpload`
    - `cd frontend && npm test -- --run useResumeUpload` exits 0 (VALIDATION 07-05-09)
    - `cd frontend && npm run typecheck` exits 0 (VALIDATION 07-05-10)
  </acceptance_criteria>
  <done>
    - api/profile.ts filled with 3 typed service functions (getProfile + uploadResume + saveProfile)
    - types.ts + useResumeUpload.ts + useResumeUpload.test.tsx committed
    - Zero backend changes in this task — purely consumes Plan 04's shipped endpoints
  </done>
</task>

<task type="auto" id="07-05-02">
  <name>Task 2: ProfileView + ResumeUploader + SkillDiffChip + ReviewPanel components + tests</name>
  <files>frontend/src/components/profile/ProfileView.tsx, frontend/src/components/profile/ResumeUploader.tsx, frontend/src/components/profile/SkillDiffChip.tsx, frontend/src/components/profile/ReviewPanel.tsx, frontend/src/components/profile/ProfileView.test.tsx, frontend/src/components/profile/ResumeUploader.test.tsx, frontend/src/components/profile/SkillDiffChip.test.tsx, frontend/src/components/profile/ReviewPanel.test.tsx</files>
  <read_first>
    - frontend/src/components/dashboard/TopSkillsCard.tsx (lines 83-138 — Card + useQuery + Skeleton/Alert/EmptyState pattern)
    - frontend/src/components/chat/ChatComposer.tsx (lines 73-113 — sticky input + Button pattern)
    - frontend/src/components/chat/useChatStream.ts (cold-start setTimeout pattern lines 24, 174-177)
    - frontend/src/components/ui/{card,button,badge,input,skeleton,alert,sonner}.tsx (existing primitives)
    - frontend/src/components/EmptyState.tsx (analog for empty current-skills surface)
    - .planning/phases/07-profile-resume-upload/07-UI-SPEC.md (visual contract — read sections covering ProfileView, ResumeUploader, SkillDiffChip, ReviewPanel)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §17-20 (component analogs lines 695-841)
    - .planning/phases/07-profile-resume-upload/07-CONTEXT.md §D-24..D-31 (UX decisions)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §10 (chip UX + inline edit lines 421-466)
  </read_first>
  <action>
**Step A — `frontend/src/components/profile/ProfileView.tsx`** (read-only current skills surface per PATTERNS §17). Consumes the now-existing GET /profile endpoint via `getProfile()` (shipped by Plan 04 Task 3):

    import { useQuery } from '@tanstack/react-query'
    import { AlertCircle } from 'lucide-react'
    import { getProfile } from '@/api/profile'
    import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
    import { Badge } from '@/components/ui/badge'
    import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
    import { Skeleton } from '@/components/ui/skeleton'
    import { EmptyState } from '@/components/EmptyState'

    export function ProfileView() {
      const { data, isPending, isError, error } = useQuery({
        queryKey: ['profile'],
        queryFn: ({ signal }) => getProfile(signal),
        staleTime: 5 * 60_000,
      })

      return (
        <Card data-testid="profile-view">
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Current skills{data ? ` (${data.skills.length})` : ''}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isPending && (
              <div className="flex flex-wrap gap-2">
                {[...Array(12)].map((_, i) => (
                  <Skeleton key={i} className="h-6 w-20" />
                ))}
              </div>
            )}
            {isError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Could not load profile</AlertTitle>
                <AlertDescription>{(error as Error).message}</AlertDescription>
              </Alert>
            )}
            {!isPending && !isError && data && data.skills.length === 0 && (
              <EmptyState
                heading="No skills yet"
                body="Upload your resume below to seed your profile."
              />
            )}
            {!isPending && !isError && data && data.skills.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {[...data.skills]
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map((s) => (
                    <Badge key={s.name} variant="secondary">{s.name}</Badge>
                  ))}
              </div>
            )}
          </CardContent>
        </Card>
      )
    }

**Step B — `frontend/src/components/profile/ResumeUploader.tsx`** (per D-30, D-31, PATTERNS §18):

Component props:

    type Props = {
      onUpload: (file: File) => void
      isPending: boolean
      isError: boolean
      error?: Error | null
    }

Behavior:
- `<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document">` styled as a dashed border drop zone
- Drag/drop listeners on wrapper div (`onDragOver` preventDefault + visual hint; `onDrop` reads `e.dataTransfer.files[0]`)
- Client-side pre-check: reject if `file.size > 2_000_000` (toast: "File too large — must be ≤2 MB"); reject if extension not in `{.pdf, .docx}` (toast: "Unsupported format — PDF or DOCX")
- Selected-file preview: filename + size + Remove (X icon) button
- Upload trigger: explicit "Upload" button (not auto-submit on file pick)
- During `isPending`:
  - 0-2s: copy `"Reading your resume…"`
  - 2-10s: copy `"Asking the agent to extract skills…"`
  - 10s+: copy `"Still working — extraction can take a minute on first load…"`
  - Implemented via `useEffect` + two `setTimeout` calls similar to `useChatStream.ts:24,174-177`. Clean up timers on `isPending` going false or on unmount
- Error display: shows the backend `reason` token via the COPY mapping (D-35):

      const COPY: Record<string, { title: string; body: string }> = {
        file_too_large: { title: 'File too large', body: 'Resume must be ≤2 MB.' },
        unsupported_file_type: { title: 'Unsupported format', body: 'Upload a PDF or DOCX.' },
        pdf_encrypted: { title: 'Encrypted PDF', body: 'Remove the password and try again.' },
        text_extraction_failed: { title: "Could not read the file", body: 'Scanned image; v1 does not support OCR.' },
        extraction_failed: { title: 'Extraction failed', body: 'The agent could not parse the resume. Try again or simplify formatting.' },
        empty_skills: { title: 'No skills found', body: 'The extracted skill list is empty. Is this a resume?' },
        llm_unavailable: { title: 'Service unavailable', body: 'The LLM is down. Try again in a few minutes.' },
      }

Use shadcn `sonner` for toasts (already shipped); use `lucide-react` icons `Upload`, `FileText`, `X`.

**Step C — `frontend/src/components/profile/SkillDiffChip.tsx`** (per D-24, D-26, PATTERNS §20):

Props:

    type Props = {
      item: DiffItemState
      onToggle: (name: string) => void
      onRename: (name: string, newName: string) => void
    }

Behavior:
- Status pill via `Badge` with className per D-24:
  - added: `bg-green-500/10 text-green-700 dark:text-green-400` + label "+ ADDED"
  - removed: `bg-red-500/10 text-red-700 dark:text-red-400` + label "− REMOVED"
  - unchanged: `bg-muted text-muted-foreground` + label "= UNCHANGED"
- Tick affordance: native `<input type="checkbox" checked={item.checked} onChange={() => onToggle(item.name)}>` wrapped in `<label>` so click anywhere toggles (RESEARCH §10 Option A)
- Name display:
  - Default: `<span>{item.editedName}</span>` (or `item.name` when not yet edited)
  - When `editing` state: `<Input>` with autoFocus; Enter saves + calls `onRename(originalName, draft)`; Escape cancels + reverts draft
- Pencil affordance: visible ONLY when `item.editable === true` (added chips); `<Button variant="ghost" size="icon" onClick={() => setEditing(true)}><Pencil className="h-3 w-3" /></Button>`
- Removed and unchanged chips: read-only name, no Pencil

Inline-edit pattern from RESEARCH §10 lines 435-457.

**Step D — `frontend/src/components/profile/ReviewPanel.tsx`** (per D-27, PATTERNS §19):

Props:

    type Props = {
      diff: DiffItemState[]
      extractionId: string
      onSave: (payload: UserProfileUpdate) => void
      onCancel: () => void
      isSaving: boolean
      setDiff: (diff: DiffItemState[]) => void  // for chip toggle/rename callbacks
    }

Layout (per D-27 verbatim):

    <Card>
      <CardHeader>
        <CardTitle>Review extracted skills</CardTitle>
        <CardDescription>
          {n_extracted} skills found · {n_added} new · {n_removed} removed · {n_unchanged} unchanged
        </CardDescription>
      </CardHeader>
      <CardContent className="max-h-[60vh] overflow-y-auto">
        <ul className="space-y-1">
          {diff.map(item => (
            <SkillDiffChip
              key={item.name}
              item={item}
              onToggle={handleToggle}
              onRename={handleRename}
            />
          ))}
        </ul>
      </CardContent>
      <CardFooter className="sticky bottom-0 bg-background border-t flex justify-between">
        <Button variant="outline" onClick={onCancel} disabled={isSaving}>Discard</Button>
        <Button onClick={handleSave} disabled={isSaving}>
          Save profile ({checkedCount} skills)
        </Button>
      </CardFooter>
    </Card>

Live counts computed from diff state. Save handler composes the `UserProfileUpdate` payload:

    function handleSave() {
      const skills = diff
        .filter(d => d.checked)
        .map(d => ({ name: d.editedName }))
      onSave({
        skills,
        target_roles: null,
        preferred_locations: null,
        min_salary_eur: null,
        remote_preference: null,
        extraction_id: extractionId,
      })
    }

**Step E — Component tests** per VALIDATION 07-05-05, 07-05-06, 07-05-07, 07-05-08:

`ProfileView.test.tsx`:
- Mock `@/api/profile.getProfile` to return a `UserSkillProfile` with 3 skills; render with `QueryClientProvider`; assert `getByText('Current skills (3)')`; assert all 3 skills appear as Badge children
- Loading state: mock getProfile to return a never-resolving Promise (or no mock); assert skeleton elements present
- Error state: mock getProfile to reject; assert `getByText('Could not load profile')`

`ResumeUploader.test.tsx`:
- File input has `accept` attribute including `.pdf,.docx`
- Drop a `.txt` file → toast / inline error / does NOT call `onUpload`
- Drop a 3 MB PDF → toast / does NOT call `onUpload`
- Drop a 100 KB valid PDF → calls `onUpload(file)` after clicking Upload button
- During `isPending=true`: first 2s shows "Reading your resume…"; advance fake timer to 2s+ → "Asking the agent…"; advance to 10s+ → "Still working…"

`SkillDiffChip.test.tsx`:
- Added chip: green pill + "+ ADDED" + Pencil icon visible
- Removed chip: red pill + "− REMOVED" + NO Pencil
- Unchanged chip: muted pill + "= UNCHANGED" + NO Pencil
- Click Pencil on added → Input renders + focused
- Enter on Input → calls `onRename(originalName, draftValue)` with edited value
- Escape on Input → no onRename call; chip reverts to span with original name
- Click checkbox → calls `onToggle(name)`

`ReviewPanel.test.tsx`:
- Renders summary count: "X skills found · Y new · Z removed · W unchanged" matches diff prop
- Footer is sticky (assert className `sticky bottom-0`)
- Save button label updates live: untick an "added" chip → button count decreases by 1
- Click Save → `onSave` called with payload containing only ticked items as skills + extraction_id
- Click Discard → `onCancel` called

Run:

    cd frontend && npm test -- --run profile/
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; npm run typecheck &amp;&amp; npm test -- --run ProfileView ResumeUploader SkillDiffChip ReviewPanel</automated>
  </verify>
  <acceptance_criteria>
    - 4 component source files + 4 test files committed
    - `cd frontend && npm test -- --run ProfileView` passes (VALIDATION 07-05-05)
    - `cd frontend && npm test -- --run ResumeUploader` passes (VALIDATION 07-05-06)
    - `cd frontend && npm test -- --run SkillDiffChip` passes (VALIDATION 07-05-07)
    - `cd frontend && npm test -- --run ReviewPanel` passes (VALIDATION 07-05-08)
    - `cd frontend && npm run typecheck` exits 0
    - `ls frontend/src/components/profile/*.{ts,tsx} | wc -l` >= 11 (6 source + 5 test files; .gitkeep can be removed)
  </acceptance_criteria>
  <done>
    - All 4 component + 4 test files green
    - Status pill colors match D-24 verbatim
    - Cold-start stepped copy works in ResumeUploader test
  </done>
</task>

<task type="auto" id="07-05-03">
  <name>Task 3: Profile.tsx page composition + integration smoke</name>
  <files>frontend/src/routes/Profile.tsx</files>
  <read_first>
    - frontend/src/routes/Profile.tsx (current: PhasePlaceholder stub — must be replaced)
    - frontend/src/routes/Dashboard.tsx (composition analog)
    - frontend/src/routes/Chat.tsx (composition analog)
    - frontend/src/components/profile/* (just-written components)
    - .planning/phases/07-profile-resume-upload/07-CONTEXT.md §D-28 (idle / reviewing state machine)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §24 (route composition pattern lines 956-993)
  </read_first>
  <action>
**Step A — Rewrite `frontend/src/routes/Profile.tsx`** (replacing PhasePlaceholder) per D-28 + PATTERNS §24:

    import { useState } from 'react'
    import { ProfileView } from '@/components/profile/ProfileView'
    import { ResumeUploader } from '@/components/profile/ResumeUploader'
    import { ReviewPanel } from '@/components/profile/ReviewPanel'
    import { useResumeUpload } from '@/components/profile/useResumeUpload'
    import type { DiffItemState } from '@/components/profile/types'

    export function ProfilePage() {
      const { state, setState, upload, save, reset } = useResumeUpload()

      function updateDiff(updater: (diff: DiffItemState[]) => DiffItemState[]) {
        if (state.phase === 'reviewing') {
          setState({ ...state, diff: updater(state.diff) })
        }
      }

      if (state.phase === 'reviewing') {
        return (
          <div className="container py-6">
            <ReviewPanel
              diff={state.diff}
              extractionId={state.extractionId}
              onSave={(payload) => save.mutate(payload)}
              onCancel={reset}
              isSaving={save.isPending}
              setDiff={(diff) => setState({ ...state, diff })}
            />
          </div>
        )
      }

      // 'idle' and 'saved' both surface the ProfileView + Uploader
      return (
        <div className="container py-6 space-y-6">
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

Confirm the route is the default-exported component, OR matches whatever import shape `frontend/src/App.tsx` expects (check `App.tsx` routes definition to confirm).

**Step B — Smoke verifications:**

    # No PhasePlaceholder reference
    grep PhasePlaceholder frontend/src/routes/Profile.tsx && exit 1 || echo OK

    # Build smoke
    cd frontend && npm run typecheck
    cd frontend && npm run build

    # Existing tests still pass
    cd frontend && npm test -- --run

If `App.tsx` imports `ProfilePage` as a named import, keep `export function ProfilePage`. If it imports as default, add `export default ProfilePage`.
  </action>
  <verify>
    <automated>! grep PhasePlaceholder frontend/src/routes/Profile.tsx &amp;&amp; cd frontend &amp;&amp; npm run typecheck &amp;&amp; npm run build &amp;&amp; npm test -- --run</automated>
  </verify>
  <acceptance_criteria>
    - `! grep PhasePlaceholder frontend/src/routes/Profile.tsx` exits 0 (VALIDATION 07-05-04)
    - `cd frontend && npm run typecheck` exits 0 (VALIDATION 07-05-10)
    - `cd frontend && npm run build` succeeds (production build smoke)
    - `cd frontend && npm test -- --run` exits 0 (all suites green, including existing Phase 4/5/6 tests)
    - `ls frontend/src/components/profile/*.{ts,tsx} | wc -l` >= 6 source files (VALIDATION 07-05-02)
  </acceptance_criteria>
  <done>
    - Profile.tsx no longer renders PhasePlaceholder
    - Full frontend suite green
    - Production build succeeds
    - Phase 7 feature complete end-to-end
  </done>
</task>

</tasks>

<verification>
After all three tasks land, run from repo root:

```bash
# Static — feature folder has the 6+5 file count
test "$(ls frontend/src/components/profile/*.ts frontend/src/components/profile/*.tsx 2>/dev/null | wc -l | tr -d ' ')" -ge 11

# Static — PhasePlaceholder removed
! grep PhasePlaceholder frontend/src/routes/Profile.tsx

# Static — service exports (all 3: getProfile, uploadResume, saveProfile)
grep -E "export.*(uploadResume|saveProfile|getProfile)" frontend/src/api/profile.ts

# Static — OpenAPI snapshot up-to-date (from Plan 04, NOT regenerated here)
grep -E '"ResumeUploadResponse"|"SkillDiffItem"' frontend/openapi.snapshot.json

# Type + tests
cd frontend && npm run typecheck
cd frontend && npm test -- --run

# Production build
cd frontend && npm run build

# Full backend suite still green (regression — Plan 04's backend untouched here)
uv run pytest tests/ -x
```

All commands must exit 0.
</verification>

<success_criteria>
- PROF-05 closed: status-pill review panel + inline edit on added chips + tick toggles + sticky footer save
- PROF-06 (frontend half) closed: save mutation invalidates ['profile'] AND ['dashboard'] keys; `extraction_id` carried through PATCH for Langfuse correlation
- Visual contract matches UI-SPEC.md (D-24 status pill colors, D-25 default tick states, D-31 cold-start stepped copy)
- No regression in Phase 4/5/6 frontend tests
- All 10 VALIDATION 07-05-* gates green
- Zero backend mutations introduced by this plan (all backend work done by Plan 04 per CHECKER-FIX-1)
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-05-SUMMARY.md` capturing:
- Final file count under `frontend/src/components/profile/`
- Whether `react-dropzone` was avoided (D-30 — native input + drag-drop only)
- Notes on any fake-timer setup required for the cold-start stepped-copy test
- Snapshot of the production build size if `npm run build` reports it (portfolio metric)
- Confirmation that no backend files were touched by this plan (per CHECKER-FIX-1 scope discipline)
</output>
