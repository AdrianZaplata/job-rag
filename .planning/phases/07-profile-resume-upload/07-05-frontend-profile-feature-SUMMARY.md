---
phase: 07-profile-resume-upload
plan: 05
subsystem: frontend
tags: [tanstack-mutation, react-19, vitest, rtl, profile-review, prof-05, prof-06]

# Dependency graph
requires:
  - phase: 07-profile-resume-upload (Plan 04)
    provides: "GET /profile + POST /profile/upload + PATCH /profile endpoints; frontend/openapi.snapshot.json + frontend/src/api/types.ts regenerated with ResumeUploadResponse/SkillDiffItem/UserProfileUpdate/UserSkillProfile schemas"
  - phase: 07-profile-resume-upload (Plan 01)
    provides: "frontend/src/components/profile/ directory committed via .gitkeep (this plan removed the .gitkeep once real tracked files landed)"
  - phase: 04-frontend-shell-auth
    provides: "authedFetch (FormData + JSON body support); typed service module pattern per D-15; AuthGate-wrapped routes; shadcn primitives (Card/Badge/Button/Input/Alert/Skeleton/Sonner)"
  - phase: 05-dashboard
    provides: "feature-folder pattern (components/dashboard/); TanStack Query keying ['dashboard', ...] — invalidated by this plan's save mutation per D-22"
  - phase: 06-chat
    provides: "feature-folder pattern (components/chat/) + cold-start stepped-copy timer (useChatStream COLD_START_DELAY_MS) — this plan's ResumeUploader analog uses the same setTimeout cleanup pattern for D-31 stepped copy"
provides:
  - "frontend/src/api/profile.ts — getProfile / uploadResume / saveProfile typed service module"
  - "frontend/src/components/profile/types.ts — DiffItemState (SkillDiffItem + checked + editedName) + ReviewState union"
  - "frontend/src/components/profile/useResumeUpload.ts — TanStack mutation hook with idle/reviewing/saved phase machine + D-22 cache invalidation"
  - "frontend/src/components/profile/ProfileView.tsx — read-only current-skills surface"
  - "frontend/src/components/profile/ResumeUploader.tsx — native input + drag-drop + D-30 client pre-check + D-31 stepped status + D-35 verbatim COPY map"
  - "frontend/src/components/profile/SkillDiffChip.tsx — chip atom with D-24 status pill colours + D-26 inline-edit restricted to added"
  - "frontend/src/components/profile/ReviewPanel.tsx — single Card with sticky CardFooter per D-27 + live Save profile (N skills) label"
  - "frontend/src/routes/Profile.tsx — page composition replacing PhasePlaceholder (closes PROF-05)"
  - "25 new vitest+RTL tests across 5 spec files; PROF-05 + frontend half of PROF-06 closed"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Native <input type=\"file\"> + drag-drop wrapper (D-30 verbatim — NO react-dropzone): file input is hidden + accessed via ref; wrapper div carries the onDragOver/onDrop listeners + data-dragover attribute for visual hint"
    - "Stepped status copy via dual setTimeout (2s + 10s thresholds) cleaned up in useEffect return — mirrors useChatStream COLD_START_DELAY_MS pattern but extended to two thresholds per D-31"
    - "Inline-edit affordance restricted by item.source — Pencil button + Input swap only when source==='added'; onMouseDown (not onClick) on the commit/cancel buttons so they beat the Input's onBlur cancel"
    - "Backend D-35 COPY error mapping moved into the ResumeUploader component (not the hook) — keeps the hook a pure state-machine and lets the component own user-facing copy"
    - "Save mutation invalidates ['dashboard'] family in addition to ['profile'] — Phase 5 CV-vs-market widget reads profile server-side, so cache propagation needs both keys (D-22)"

key-files:
  created:
    - frontend/src/components/profile/ProfileView.tsx
    - frontend/src/components/profile/ResumeUploader.tsx
    - frontend/src/components/profile/SkillDiffChip.tsx
    - frontend/src/components/profile/ReviewPanel.tsx
    - frontend/src/components/profile/useResumeUpload.ts
    - frontend/src/components/profile/types.ts
    - frontend/src/components/profile/ProfileView.test.tsx
    - frontend/src/components/profile/ResumeUploader.test.tsx
    - frontend/src/components/profile/SkillDiffChip.test.tsx
    - frontend/src/components/profile/ReviewPanel.test.tsx
    - frontend/src/components/profile/useResumeUpload.test.tsx
  modified:
    - frontend/src/api/profile.ts
    - frontend/src/routes/Profile.tsx
  deleted:
    - frontend/src/components/profile/.gitkeep

key-decisions:
  - "ResumeUploader owns the D-35 COPY error map (not useResumeUpload): keeps the hook pure state-machine; the component renders user-facing copy directly from the Error.message which carries the backend reason token from profile.ts"
  - "Client-side validation allows EITHER extension OR MIME match (not strict AND): some browsers fail to set file.type for DOCX, but the .docx extension still proves intent; backend D-08 is the canonical AND-gate"
  - "Pencil-edit commit uses onMouseDown — not onClick — to beat the Input's onBlur cancel handler. Without this, clicking the Check button cancels the edit instead of committing it"
  - "Removed frontend/src/components/profile/.gitkeep — Plan 01 created it to track the empty directory; with 11 real tracked files now in place the .gitkeep is redundant. Documented as a deletion in key-files"
  - "ReviewPanel keeps internal localDiff state and mirrors changes back to parent via setDiff prop — this matches the plan's prop shape exactly (setDiff is forwarded to keep the upstream ReviewState.diff array in sync for callers that want it)"

patterns-established:
  - "Feature-folder Phase 7 mirror — 6 source files + 5 test files under components/profile/, single typed service module under api/profile.ts, single hook owning the entire upload+review lifecycle"
  - "Two-state route composition (idle/reviewing) backed by a discriminated-union state machine — simpler than nested routes for an in-memory ephemeral draft (matches CHAT-06 refresh-clears-state precedent)"

requirements-completed: [PROF-05, PROF-06]

# Metrics
duration: ~7m
completed: 2026-05-28
---

# Phase 07 Plan 05: Frontend Profile Feature Summary

**Shipped the Phase 7 frontend feature folder: 6 source files + 5 vitest+RTL tests under `frontend/src/components/profile/`, filled `frontend/src/api/profile.ts` with three typed service functions (getProfile / uploadResume / saveProfile), and replaced `frontend/src/routes/Profile.tsx`'s `PhasePlaceholder` with a real two-state composition (idle → ProfileView+ResumeUploader, reviewing → ReviewPanel with sticky footer). 25 new tests green; full frontend suite 113 tests pass; production build clean (Profile chunk 16.12 kB / 5.72 kB gzipped). PROF-05 closed; PROF-06 frontend half closed via D-22 save-mutation cache invalidation of both `['profile']` AND `['dashboard']`. Zero backend mutations.**

## Performance

- **Duration:** ~7 min (start 11:22:43Z → SUMMARY 11:29:25Z)
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 3
- **Files created:** 11
- **Files modified:** 2
- **Files deleted:** 1 (`.gitkeep` redundancy)

## Accomplishments

- **`frontend/src/api/profile.ts` (filled, 71 lines).** Replaces the existing 5-line stub. Three typed service functions: `getProfile(signal?)` → `UserSkillProfile`, `uploadResume(file, signal?)` → `ResumeUploadResponse` (multipart/form-data POST), `saveProfile(payload, signal?)` → `UserSkillProfile` (PATCH JSON). All wrap `authedFetch`. `uploadResume` deliberately does NOT set Content-Type so the browser fills in the multipart boundary; on non-200 it parses the backend's `{detail: {reason, message}}` shape (D-35) and throws an Error whose `message` carries the bare reason token — downstream components map that to user-facing copy.

- **`frontend/src/components/profile/types.ts` (NEW, 51 lines).** `DiffItemState = SkillDiffItem & { checked: boolean; editedName: string }` per D-29 verbatim. `ReviewState` discriminated union per D-28: `{ phase: 'idle' } | { phase: 'reviewing'; diff; extractionId } | { phase: 'saved' }`. Re-exports the four codegen schema types for downstream component imports.

- **`frontend/src/components/profile/useResumeUpload.ts` (NEW, 64 lines).** Single hook owning the entire upload + review lifecycle. Two TanStack `useMutation` hooks (`upload` + `save`) + a `useState` phase machine. On `upload.onSuccess`, hydrates `DiffItemState[]` with D-25 default tick states (`added` and `unchanged` checked; `removed` unchecked) and captures `extraction_id`. On `save.onSuccess`, calls `queryClient.setQueryData(['profile'], profile)` AND `queryClient.invalidateQueries({queryKey: ['dashboard']})` — closing PROF-06's "save propagates to dashboard" half. `reset()` returns to idle.

- **`frontend/src/components/profile/ProfileView.tsx` (NEW, 79 lines).** Read-only current-skills surface. `useQuery({queryKey: ['profile']})` → `getProfile`. Renders a Card with `Current skills (N)` header and alphabetical (case-insensitive) secondary Badge chips. 4 surface states: loading (12 Skeleton placeholders + `role="status" aria-label="Loading profile"`), error (destructive Alert with the Error.message), empty (EmptyState with `User` icon — defensive guard; Phase 1 D-08 seeds the row), success (chip grid).

- **`frontend/src/components/profile/ResumeUploader.tsx` (NEW, 268 lines).** Card + drop-zone + selected-file pill + stepped status copy + inline error Alert. Hidden `<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document">` accessed via ref; wrapper `<div role="button" tabIndex={0}>` carries the drag-drop listeners + `data-dragover` attribute. Client-side `validateFile()` rejects size > 2_000_000 OR extension not in `.pdf/.docx` BEFORE POST (T-07-02 / T-07-05 mitigation). During `isPending`: `useEffect` arms two `setTimeout` calls (2s → "Asking the agent to extract skills…", 10s → "Still working — extraction can take a minute on first load…"); cleanup clears both. Error rendering: client-validation error takes precedence; otherwise maps `error.message` through the D-35 verbatim COPY object (`file_too_large`, `unsupported_file_type`, `pdf_encrypted`, `text_extraction_failed`, `extraction_failed`, `empty_skills`, `llm_unavailable`).

- **`frontend/src/components/profile/SkillDiffChip.tsx` (NEW, 156 lines).** Single chip row: native checkbox + status pill Badge + skill name display (or shadcn Input when editing) + Pencil/Save/Cancel icon buttons. D-24 verbatim status pill classes: added → `bg-green-500/10 text-green-700 dark:text-green-400 / "+ ADDED"`, removed → `bg-red-500/10 text-red-700 dark:text-red-400 / "− REMOVED"` (U+2212), unchanged → `bg-muted text-muted-foreground / "= UNCHANGED"`. Inline-edit restricted to `item.source === 'added'` per D-26. Enter → `commitEdit()` calls `onRename(originalName, trimmedDraft)`; Escape → `cancelEdit()`. Commit/Cancel icon buttons use `onMouseDown` (not `onClick`) so they fire BEFORE the Input's `onBlur` cancel — without this, clicking Save would cancel instead of committing.

- **`frontend/src/components/profile/ReviewPanel.tsx` (NEW, 144 lines).** Single shadcn `<Card>` with sticky `<CardFooter>` per D-27. Owns the local `DiffItemState[]` and mirrors changes back via the parent's `setDiff` prop. Live counts in `<CardDescription>`: `{n_extracted} skills found · {n_added} new · {n_removed} removed · {n_unchanged} unchanged`. Save button label live-updates to `Save profile (N skills)` (singular/plural correct); disabled when `checkedTotal === 0` (prevents accidental empty-save). On Save: composes `UserProfileUpdate` with `skills = checked.map({ name: editedName })`, all other fields `null`, `extraction_id` from props.

- **`frontend/src/routes/Profile.tsx` (rewritten).** Replaces the `PhasePlaceholder` stub. Single `useResumeUpload()` call drives the state machine; conditional render: `state.phase === 'reviewing'` → ReviewPanel; otherwise → ProfileView + ResumeUploader. Container layout is `mx-auto w-full max-w-3xl px-6 py-6 space-y-6` matching the Phase 6 chat reading-width precedent.

- **25 new tests, all green.** 4 ProfileView + 7 ResumeUploader + 7 SkillDiffChip + 7 ReviewPanel + 3 useResumeUpload. ResumeUploader test uses `vi.useFakeTimers()` + `vi.advanceTimersByTime()` to exercise the stepped status-copy transitions (0-2s / 2-10s / 10s+). SkillDiffChip tests assert the D-24 class strings literally (`bg-green-500/10`, `bg-red-500/10`, `bg-muted`). ReviewPanel tests verify the sticky footer class + live count + Save payload shape + Discard wiring + disabled-when-empty + Saving… disabled state.

- **Production build green.** `npm run build` succeeds: `dist/assets/Profile-ArEP0ROo.js` chunk = 16.12 kB (5.72 kB gzipped). No new chunks beyond expected per-route lazy splits.

- **Zero backend mutations.** This plan purely consumes the artifacts Plan 04 shipped (CHECKER-FIX-1 scope discipline). `git diff master..HEAD -- src/ tests/ alembic/ pyproject.toml` after Plan 05's three commits is identical to `git diff master..[Plan 04 head]` — confirmed by spot-check.

## Task Commits

1. **Task 1: api/profile.ts + types.ts + useResumeUpload + 3 hook tests** — `6f147e2` (feat)
2. **Task 2: 4 components + 4 component tests (+ .gitkeep removal)** — `316ca56` (feat)
3. **Task 3: Profile.tsx route composition** — `44a8f6f` (feat)

## Files Created/Modified

Created:
- `frontend/src/components/profile/types.ts` (51 lines)
- `frontend/src/components/profile/useResumeUpload.ts` (64 lines)
- `frontend/src/components/profile/useResumeUpload.test.tsx` (191 lines)
- `frontend/src/components/profile/ProfileView.tsx` (79 lines)
- `frontend/src/components/profile/ProfileView.test.tsx` (76 lines)
- `frontend/src/components/profile/ResumeUploader.tsx` (268 lines)
- `frontend/src/components/profile/ResumeUploader.test.tsx` (197 lines)
- `frontend/src/components/profile/SkillDiffChip.tsx` (156 lines)
- `frontend/src/components/profile/SkillDiffChip.test.tsx` (147 lines)
- `frontend/src/components/profile/ReviewPanel.tsx` (144 lines)
- `frontend/src/components/profile/ReviewPanel.test.tsx` (175 lines)

Modified:
- `frontend/src/api/profile.ts` (5 lines → 71 lines)
- `frontend/src/routes/Profile.tsx` (6 lines → 53 lines)

Deleted:
- `frontend/src/components/profile/.gitkeep` (Plan 01 directory-marker; redundant once real files landed)

## Decisions Made

- **Error COPY in component, not hook.** Plan 05 PATTERNS draft (and the plan's `<action>` for Task 1) hinted at putting the COPY map in `useResumeUpload`. I moved it to `ResumeUploader.tsx` because the hook is a pure state-machine; user-facing copy is presentation. The hook's `upload.error` is an `Error` whose `message` carries the bare D-35 reason token; the component maps that token to `{title, body}`. Net: same behaviour, cleaner separation.
- **Client-side validation is permissive on type OR ext.** Plan 04 backend gate is `extension AND Content-Type` (D-08). The frontend validates `extension OR Content-Type` — that's intentional. Browsers sometimes set `file.type === ""` for `.docx`; rejecting client-side on a missing MIME would be a false negative. The backend's strict AND-gate remains the canonical security boundary; client-side is a UX nicety per D-30.
- **react-dropzone NOT installed (D-30 verbatim).** Confirmed: zero new npm dependencies. Native `<input type="file">` + custom `onDragOver` / `onDrop` listeners on the wrapper `<div role="button">`. Two outcomes: drag-over visual feedback via `data-dragover="true/false"` attribute, and dropping a file is routed through the same `handleCandidate()` path as the file picker.
- **`onMouseDown` for inline-edit commit/cancel buttons.** When the user clicks the green Check (commit) icon while editing, the Input's `onBlur` fires the cancel handler FIRST (mousedown → blur → click). To beat that race, the commit/cancel buttons use `onMouseDown` + `e.preventDefault()` instead of `onClick`. Discovered in test write-up, not a runtime bug, but documented as a deliberate pattern.
- **`.gitkeep` deleted.** Plan 01 committed it to make the directory tracked; once Plan 05 lands 11 real `.ts`/`.tsx` files the marker is redundant + slightly misleading (a future grep for "empty Phase 7 directory" would surface it as a false positive). The deletion is a Rule 2 (auto-remove redundant artifact) cleanup, not a behavior change.
- **`Save profile (N skills)` instead of `Save (N new · M keep removed · K unchanged)`.** The plan's `<action>` ReviewPanel JSX skeleton showed `Save profile (N skills)`. UI-SPEC §10 also lists `Save (N new · M keep removed · K unchanged)` as the D-25 verbatim long-form label. I went with the shorter `Save profile (N skills)` per the plan's action-block instruction. Both are contract-compliant per CONTEXT D-25 ("save button's summary label updates live") — the count is the load-bearing signal. The shorter form is more scannable in a single sticky footer; the longer form fits if the user wants per-bucket transparency. If portfolio UAT prefers the longer label, a 1-line change in `ReviewPanel.tsx` swaps it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SkillDiffChip test helper had stale `editedName` default**

- **Found during:** Task 2 first test run (`SkillDiffChip > clicking Pencil enters edit mode...`)
- **Issue:** The `diffItem()` test helper applied defaults `{ name: 'Python', editedName: 'Python' }` THEN spread `over` (the test override). When a caller passed `{ name: 'Rust', source: 'added' }`, the `name` field updated correctly but `editedName` stayed `'Python'` because the spread didn't override it. The first edit-mode assertion (`input.value === 'Rust'`) failed: `expected 'Python' to be 'Rust'`.
- **Fix:** Rewrote the helper to compute `editedName: over.editedName ?? merged.name` AFTER the merge. Now `diffItem({ name: 'Rust' })` produces `editedName: 'Rust'` unless the caller explicitly overrode it.
- **Files modified:** `frontend/src/components/profile/SkillDiffChip.test.tsx`
- **Commit:** `316ca56` (folded into the Task 2 commit since the failure surfaced during the same red→green cycle)

**Total deviations:** 1 auto-fixed (Rule 1 - Bug; test helper logic error).
**Impact on plan:** None — the corrected helper exercises the documented `DiffItemState` shape more rigorously. Production code unaffected.

## Issues Encountered

- **Pre-existing `test_alembic.py` failures without DATABASE_URL.** Same situation Plan 04 SUMMARY documented: two tests crash with `KeyError: 'DATABASE_URL'` at module-import time when the variable is unset. Plan 05 doesn't touch backend; verification ran with DATABASE_URL set (260 passed). Plan 02's `deferred-items.md` already tracks this; not a Plan 05 regression.

## User Setup Required

None. The frontend feature consumes shipped backend endpoints + existing OpenAPI codegen types + existing shadcn primitives + lucide icons. Zero new npm dependencies (D-30 verbatim).

## Notable Implementation Notes

- **react-dropzone NOT used** (D-30 verbatim). Confirmed: `grep react-dropzone frontend/package.json` returns no matches; the drop-zone is a styled `<div role="button">` with `onDrop`/`onDragOver` listeners + a hidden `<input type="file">`.
- **Fake-timer setup for D-31 cold-start test.** `vi.useFakeTimers()` in a `describe` block's `beforeEach`; `vi.advanceTimersByTime(2_001)` exercises the 2s → "Asking the agent…" transition; another `advanceTimersByTime(10_000)` exercises the 10s+ → "Still working…" transition. Cleanup via `afterEach(() => vi.useRealTimers())`. The component cleans both timers in its `useEffect` return so unmounting mid-pending does not leak timers.
- **Production build size.** `dist/assets/Profile-ArEP0ROo.js` = 16.12 kB raw, 5.72 kB gzipped. Comparable to the Phase 5 Dashboard chunk (325 kB raw, 99 kB gzipped — Dashboard pulls in recharts) and the Phase 6 Chat chunk (16.3 kB raw, 5.9 kB gzipped). Profile chunk size dominated by the SkillDiffChip + ReviewPanel logic (~300 lines combined post-tree-shake).
- **Zero backend files touched.** `git diff master..HEAD --stat -- src/job_rag/ alembic/ tests/ pyproject.toml` is empty for the three Plan 05 commits. CHECKER-FIX-1 scope discipline honoured.

## Next Plan Readiness

Phase 7 is **plans-complete**: all 5 plans landed (Wave 0 foundation → backend load_profile flip → resume extractor → upload routes + diff + Langfuse → frontend feature folder). PROF-01 through PROF-06 closed in code; ready for `/gsd-verify-work 7` to run the verifier against the 6 must-haves.

UAT prerequisites (manual; not part of this plan):
- Set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` in staging if you want to inspect the 4-span trace per D-32
- Verify M-marker 2 (oversized 5 MB upload → DevTools Network shows 413 with content-length cap hit, body bytes ≈ 0)
- Verify M-marker 3 (Langfuse trace shows 4 spans: text_extract / llm_extract / diff_compute / profile_save)
- Verify M-marker 4 (post-save dashboard CV-vs-market widget reflects the new skill list — proves the `['dashboard']` cache invalidation works end-to-end)
- Verify M-marker 5 (inline-edit on an added chip persists through save — refresh `/profile` and confirm the renamed skill appears in `<ProfileView>`)
- Verify M-marker 6 (cold-start awareness copy transitions visible during a forced cold-start upload — set ACA min-replicas=0 + idle for 5 min + upload)

Blockers: None.

## Self-Check: PASSED

Verified after writing this SUMMARY.md:

Files exist (each command exit 0):
- `test -f frontend/src/api/profile.ts` → FOUND (71 lines)
- `test -f frontend/src/components/profile/types.ts` → FOUND
- `test -f frontend/src/components/profile/useResumeUpload.ts` → FOUND
- `test -f frontend/src/components/profile/useResumeUpload.test.tsx` → FOUND
- `test -f frontend/src/components/profile/ProfileView.tsx` → FOUND
- `test -f frontend/src/components/profile/ProfileView.test.tsx` → FOUND
- `test -f frontend/src/components/profile/ResumeUploader.tsx` → FOUND
- `test -f frontend/src/components/profile/ResumeUploader.test.tsx` → FOUND
- `test -f frontend/src/components/profile/SkillDiffChip.tsx` → FOUND
- `test -f frontend/src/components/profile/SkillDiffChip.test.tsx` → FOUND
- `test -f frontend/src/components/profile/ReviewPanel.tsx` → FOUND
- `test -f frontend/src/components/profile/ReviewPanel.test.tsx` → FOUND
- `test -f frontend/src/routes/Profile.tsx` → FOUND (rewritten)
- `! test -f frontend/src/components/profile/.gitkeep` → exit 0 (file correctly deleted)
- `ls frontend/src/components/profile/*.{ts,tsx} | wc -l` → 11

Commits exist (verified via `git log --oneline`):
- `6f147e2` → FOUND ("feat(07-05): add profile service + types + useResumeUpload hook")
- `316ca56` → FOUND ("feat(07-05): add 4 profile components + tests (ProfileView/ResumeUploader/SkillDiffChip/ReviewPanel)")
- `44a8f6f` → FOUND ("feat(07-05): replace Profile.tsx PhasePlaceholder with idle/reviewing composition")

Functional checks:
- `grep -E "export.*(uploadResume|saveProfile|getProfile)" frontend/src/api/profile.ts` → 3 export lines ✓
- `! grep PhasePlaceholder frontend/src/routes/Profile.tsx` → exit 0 ✓
- `grep -E '"ResumeUploadResponse"|"SkillDiffItem"' frontend/openapi.snapshot.json` → 2 schema definitions ✓
- `cd frontend && npm run typecheck` → exits 0 ✓
- `cd frontend && npm test -- --run` → 113 tests pass (22 test files; 25 new from Plan 05 + 88 pre-existing) ✓
- `cd frontend && npm run build` → exits 0; Profile chunk = 16.12 kB (5.72 kB gzipped) ✓
- `DATABASE_URL=... uv run pytest tests/ --deselect tests/test_alembic.py::test_0005_upgrade_populates_oid_when_env_set` → 260 passed, 18 skipped, 1 deselected (pre-existing) ✓

## Threat Flags

None. This plan ONLY consumes endpoints/schemas Plan 04 already shipped + threat-modeled. The two T-07-02 / T-07-05 mitigations in this plan's `<threat_model>` (client pre-checks on size + extension) are UX niceties — the backend's authoritative gates remain in `src/job_rag/api/middleware.py` (D-07) and `src/job_rag/api/routes.py` upload handler (D-08). No new network surface, no new trust boundary, no new schema at trust boundary.

---
*Phase: 07-profile-resume-upload*
*Plan: 05-frontend-profile-feature*
*Completed: 2026-05-28*
