---
phase: 07-profile-resume-upload
reviewed: 2026-05-28T13:35:00Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - alembic/versions/0006_seed_user_profile.py
  - frontend/src/api/profile.ts
  - frontend/src/components/profile/ProfileView.test.tsx
  - frontend/src/components/profile/ProfileView.tsx
  - frontend/src/components/profile/ResumeUploader.test.tsx
  - frontend/src/components/profile/ResumeUploader.tsx
  - frontend/src/components/profile/ReviewPanel.test.tsx
  - frontend/src/components/profile/ReviewPanel.tsx
  - frontend/src/components/profile/SkillDiffChip.test.tsx
  - frontend/src/components/profile/SkillDiffChip.tsx
  - frontend/src/components/profile/types.ts
  - frontend/src/components/profile/useResumeUpload.test.tsx
  - frontend/src/components/profile/useResumeUpload.ts
  - frontend/src/routes/Profile.tsx
  - scripts/generate_resume_fixtures.py
  - src/job_rag/api/app.py
  - src/job_rag/api/middleware.py
  - src/job_rag/api/routes.py
  - src/job_rag/config.py
  - src/job_rag/db/models.py
  - src/job_rag/extraction/resume_extractor.py
  - src/job_rag/extraction/resume_prompt.py
  - src/job_rag/mcp_server/tools.py
  - src/job_rag/models.py
  - src/job_rag/observability.py
  - src/job_rag/services/analytics.py
  - src/job_rag/services/matching.py
  - src/job_rag/services/profile.py
  - tests/conftest.py
  - tests/test_alembic.py
  - tests/test_analytics.py
  - tests/test_api.py
  - tests/test_matching.py
  - tests/test_mcp_server.py
  - tests/test_observability.py
  - tests/test_profile.py
  - tests/test_resume_extractor.py
findings:
  critical: 0
  warning: 5
  info: 8
  total: 13
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-28T13:35:00Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Summary

Phase 7 delivers the Profile + Resume Upload feature end-to-end: a 0006 seed migration, a DB-backed `load_profile` flip, a new `extract_resume` Instructor pipeline, the `POST /profile/upload` + `PATCH /profile` + `GET /profile` route trio with a 2 MB middleware guard, Langfuse correlation via `extraction_id`, plus a React profile route with diff-review UI. Test coverage is thorough — migration round-trip, 413/415/422 paths, fail-open Langfuse, PII non-leakage, frontend hook/component behaviour — and the code generally follows the project's structured-logging + Pydantic conventions cleanly.

No Critical findings. The five Warnings are concrete bugs that should be fixed before ship:

1. **`text` import shadowed inside `upload_resume`** — `from sqlalchemy import ... text ...` is reassigned to the extracted resume string. Currently a latent bug because the upload route doesn't call `text(...)` after the reassignment, but the symbol collision is a footgun any future edit will trip on.
2. **Dynamic Tailwind classes in `ResumeUploader`** — `` className={`h-6 w-${w}`} `` for `w ∈ {18, 22, 28}` produces classes that Tailwind never emits (verified against `frontend/dist/assets/index-CbLQfUQw.css`: only `w-16`, `w-20`, `w-24` survive); three of the eight skeleton bars render with no width.
3. **`compute_skills_diff` casing collision** — when current and extracted normalize to the same key with different casing (e.g., current "Fast-API", extracted "fast api"), the `unchanged` bucket emits the extracted casing AND the diff payload still references the extracted name — meaning a save that round-trips "unchanged" silently renames the user's persisted skill (no Pencil affordance offered, no consent).
4. **Pencil "no change" branch silently re-renames** — `commitEdit` treats `trimmed === item.editedName` as "discard edit" but never compares against `item.name` itself, so editing back to the canonical name still updates `editedName` differently on second edit cycles.
5. **`Profile.tsx` saved state never resets** — once `useResumeUpload` flips to `phase: 'saved'`, nothing calls `reset()`; the next upload click on the same page session works (because `upload.mutate` overrides via `setState`), but the `saved` phase has no user-visible exit and the toast referenced in `types.ts` D-28 comment is not actually wired.

Info items cover lint-level concerns (dead imports, type-safety mismatches, doc/code drift, dual size-cap constants, unused `_async_postgres_reachable` redefinition).

## Warnings

### WR-01: `text` symbol shadowed by local variable in upload_resume

**File:** `src/job_rag/api/routes.py:701`
**Issue:** Line 35 imports `text` from `sqlalchemy` (used at line 139 for `await session.execute(text("SELECT 1"))`). Inside `upload_resume`, line 701 reassigns the same name with `text = await asyncio.to_thread(_extract_pdf_text, raw)`, and the variable is then used as bytes-of-extracted-text throughout the rest of the function (lines 705, 727, 731, 745, 751, 760, 769, 805). The handler doesn't currently call `text(...)` as a SQL helper after the reassignment, so this is latent — but it's a name collision waiting to bite the next person who adds a SQL helper call inside this handler, and pyright in strict mode would flag the implicit redefinition.
**Fix:**
```python
# Rename the local to `resume_text` (or `extracted_text`) throughout
# the upload handler. Mechanical replacement, no logic change:
if suffix == ".pdf":
    resume_text = await asyncio.to_thread(_extract_pdf_text, raw)
    file_type = "pdf"
    page_count = _pdf_page_count(raw)
else:  # .docx
    resume_text = await asyncio.to_thread(_extract_docx_text, raw)
    file_type = "docx"
# ... and update every downstream `text` reference:
if len(resume_text.strip()) < 100: ...
if len(resume_text) > 50_000:
    resume_text = resume_text[:50_000]
# ... extract_resume(resume_text), lf.update_current_observation({"text": f"[REDACTED — char_count={len(resume_text)}]"})
```

### WR-02: ResumeUploader skeleton uses dynamic Tailwind class names that never compile

**File:** `frontend/src/components/profile/ResumeUploader.tsx:294-295`
**Issue:** The skeleton row uses `` className={`h-6 w-${w}`} `` over the array `[20, 24, 16, 28, 20, 24, 18, 22]`. Tailwind v4 (per the dist CSS at `frontend/dist/assets/index-CbLQfUQw.css`) scans source files for *complete literal* class names; only `w-16`, `w-20`, `w-24` are present in the compiled output. `w-18`, `w-22`, `w-28` are NOT emitted, so 3 of the 8 skeleton bars render at width 0 (or fall back to default). This is the classic "Tailwind dynamic class" pitfall (their docs call it out explicitly). The unit test never catches this because jsdom doesn't apply CSS.
**Fix:**
```tsx
// Use a static lookup from a known finite set so Tailwind sees full class
// names at scan time:
const SKELETON_WIDTHS = [
  'w-20', 'w-24', 'w-16', 'w-28', 'w-20', 'w-24', 'w-16', 'w-24',
] as const

{isPending && (
  <div className="space-y-4">
    {/* ... */}
    <div className="flex flex-wrap gap-2" aria-hidden="true">
      {SKELETON_WIDTHS.map((cls, i) => (
        <Skeleton key={i} className={`h-6 ${cls}`} />
      ))}
    </div>
  </div>
)}
```
(Or use arbitrary values like `w-[5rem]` which Tailwind always emits.)

### WR-03: compute_skills_diff loses original casing on "unchanged" rows

**File:** `src/job_rag/services/profile.py:99-121`
**Issue:** `extracted_map` is built keyed by normalized name, value = extracted casing. For the `unchanged` bucket (line 109), `extracted_map[k]` is used — meaning when current="Fast-API" / extracted="fast api" (both normalize to `"fast api"`), the diff item carries `name="fast api"` even though the user previously chose "Fast-API" as canonical. Because `editable=False` for unchanged rows (D-26), the React UI offers no rename affordance, and `ReviewPanel.handleSave` re-emits this `name` into the PATCH payload — silently overwriting the user's canonical casing on round-trip save. The test at `tests/test_profile.py:67-88` actively asserts this behaviour as expected, but the docstring at line 92-95 says the opposite ("Casing: extracted casing for added/unchanged, current casing for removed") — meaning the documented behaviour IS the bug, just intentionally chosen, and the test locks it in.
**Fix:** Decide which casing is canonical for unchanged rows. The user-intent-preserving choice is "keep the user's existing casing" for unchanged:
```python
# Use current_map (the user's canonical casing) for unchanged:
unchanged = sorted(current_map[k] for k in (ext_keys & cur_keys))
```
Update the docstring + tests/test_profile.py test_compute_skills_diff_normalizes_via_normalize_skill assertions to match (currently they assert `"python"` / `"fast api"` / `"ci cd"` which is the *extracted* casing).

### WR-04: SkillDiffChip commitEdit treats name==editedName as discard, masking legitimate edits

**File:** `frontend/src/components/profile/SkillDiffChip.tsx:79-89`
**Issue:** `commitEdit` checks `trimmed === item.editedName` and discards the edit when equal. But the comparison reference should be `item.name` (the original) — once a user renames "Rust" → "rustlang" and clicks Pencil again, `item.editedName === "rustlang"`. If the user types back the original "Rust" and hits Enter, `trimmed("Rust") !== editedName("rustlang")` so `onRename(item.name, "Rust")` fires — fine. But if they type "rustlang" again (no actual second-edit change), the discard branch fires and the `isEdited` flag in the parent state stays true because parent state still tracks `editedName="rustlang"` vs `name="Rust"` — which is correct. The actual bug surfaces in a different scenario: when the user opens the editor, doesn't change anything, and hits Enter — `commitEdit` discards instead of committing the no-op. That's fine UX. But the `setDraft(item.editedName)` reset on discard runs even when `editing` is being torn down by an upstream `setState` (e.g., parent diff reset on a new upload). The `useEffect` at line 59-61 was added to handle that case but introduces a subtle race: if `item.editedName` arrives changed AND `editing===true`, the draft is NOT reset (correct), but if the editing state flips off externally (which never happens in current code), the draft would stick.
**Fix:** Make the intent explicit and harden against future caller patterns:
```tsx
const commitEdit = () => {
  const trimmed = draft.trim()
  if (trimmed === '') {
    // Empty input → cancel, don't blank the name
    cancelEdit()
    return
  }
  if (trimmed !== item.editedName) {
    onRename(item.name, trimmed)
  }
  setEditing(false)
  setDraft(trimmed)  // sync draft even on no-op so re-enter shows committed value
}
```

### WR-05: Profile route never exits 'saved' phase; toast referenced in types.ts is not wired

**File:** `frontend/src/components/profile/useResumeUpload.ts:54` + `frontend/src/routes/Profile.tsx:38-53`
**Issue:** `types.ts:46-47` documents `saved` as "transient — flips back to `idle` after Sonner toast + cache invalidation." The hook flips to `{ phase: 'saved' }` on save success (line 54) but never calls `reset()` to return to idle, and there is no Sonner toast invocation in either the hook or the Profile route. `Profile.tsx:38-53` treats `saved` and `idle` identically as "render ProfileView + ResumeUploader," so the user can functionally use the page again — but the `saved` state itself becomes a permanent leaf that never reverts. Two consequences: (a) the unit test at `useResumeUpload.test.tsx:146` asserts `phase === 'saved'` but the user-facing contract from types.ts is "transient → idle," and (b) no toast feedback that the save succeeded. If the design intent is "saved and idle behave the same," the `saved` phase is dead state — collapse it.
**Fix:** Either wire the toast + auto-revert per the documented contract:
```tsx
// useResumeUpload.ts
import { toast } from 'sonner'

const save = useMutation({
  mutationFn: (payload: UserProfileUpdate) => saveProfile(payload),
  onSuccess: (profile) => {
    queryClient.setQueryData(['profile'], profile)
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    setState({ phase: 'saved' })
    toast.success(`Saved ${profile.skills.length} skills to your profile`)
    // Auto-revert to idle so the phase is genuinely transient (matches types.ts D-28 comment)
    setTimeout(() => setState({ phase: 'idle' }), 0)
  },
})
```
Or remove the `saved` phase from the union and document it explicitly as deferred.

## Info

### IN-01: Duplicate / dead size-cap constant in /ingest route

**File:** `src/job_rag/api/routes.py:525`
**Issue:** `MAX_UPLOAD_BYTES = 1_000_000` is hardcoded inside the `/ingest` handler while `settings.max_resume_size_bytes` exists for the resume route. Two file-upload endpoints with two unrelated caps and no shared config knob makes ops + threat-model review awkward. Not a Phase 7 regression (the constant predates this phase) but the new code highlights the inconsistency.
**Fix:** Lift to a `settings.max_ingest_size_bytes: int = Field(default=1_000_000, ge=1)` so both caps live in one place and CI/env can override.

### IN-02: Unused import in routes.py

**File:** `src/job_rag/api/routes.py:35`
**Issue:** `text` is imported from `sqlalchemy` and used only at the single `/health` line 139. With WR-01 fix renaming the local variable, this stays — but it's worth a `# noqa` audit pass to confirm none of the other one-shot imports (e.g., `select`, `update`) is over-imported.
**Fix:** None needed if `text` stays in use post-WR-01 rename; just verify.

### IN-03: `tests/test_alembic.py:_postgres_reachable` duplicated by `conftest.py:_async_postgres_reachable`

**File:** `tests/conftest.py:63-76` and `tests/test_alembic.py:53-65`
**Issue:** Two near-identical Postgres-reachability probes diverge slightly in error handling — both wrap `create_engine + SELECT 1 + dispose` in `try/except Exception: return False`. One lives in conftest, one in the test module. Drift risk if one is hardened (e.g., timeout) but not the other.
**Fix:** Move the probe to a single helper (`tests/_helpers.py` or `conftest._postgres_reachable`) and import where needed.

### IN-04: `mcp_server/tools.py` still uses sync `SessionLocal` for ingestion

**File:** `src/job_rag/mcp_server/tools.py:165, 17`
**Issue:** `_ingest_path_sync` opens `SessionLocal()` (sync engine) and calls the sync `ingest_file` wrapper while the FastAPI route was migrated off this path in Phase 6 (D-24 per `routes.py:506-511`). Functionally fine — the MCP tool runs outside an event loop in stdio mode — but the project trajectory is toward async-only DB I/O. Worth flagging as a deferred clean-up.
**Fix:** Defer for a later phase; documented as acceptable per the MCP tool path's `asyncio.to_thread(_ingest_path_sync, ...)` wrap at line 212/225.

### IN-05: `useResumeUpload` cancels in-flight upload state on remount, no AbortSignal threading

**File:** `frontend/src/components/profile/useResumeUpload.ts:28-44`
**Issue:** `mutationFn: (file: File) => uploadResume(file)` discards the `signal` parameter that `frontend/src/api/profile.ts:30` exposes. If the user navigates away mid-upload (or kills the request via DevTools), the fetch keeps running and the `onSuccess` callback eventually fires into a stale component. TanStack Query exposes the mutation signal via `({ signal }) => ...` in the v5 API.
**Fix:**
```ts
const upload = useMutation({
  mutationFn: (file: File, { signal }) => uploadResume(file, signal),
  // ...
})
```
(TanStack Query v5 syntax — verify against the project's pinned version.)

### IN-06: data/profile.json reference still loaded by one test, not by app

**File:** `tests/test_matching.py:195` (read) + `src/job_rag/config.py:24-27` (doc)
**Issue:** `test_load_profile_returns_seeded_row` reads `data/profile.json` to compare against the DB-loaded shape (cross-check that the migration seed matches the reference snapshot). `config.py` says the JSON file is "reference snapshot only" — but this test pegs CI to that file being present. If `data/` is gitignored at the container layer (as 0006_seed_user_profile.py:13 claims) but committed at the repo layer, this is fine; if anyone removes `data/profile.json` from git, that test breaks silently. Belt-and-suspenders: skip-guard the comparison if the file is absent.
**Fix:**
```python
import pathlib
@pytest.mark.asyncio
async def test_load_profile_returns_seeded_row(db_session: AsyncSession) -> None:
    profile = await load_profile(db_session, user_id=SEEDED_UUID)
    assert isinstance(profile, UserSkillProfile)
    assert len(profile.skills) > 0
    ref_path = pathlib.Path("data/profile.json")
    if not ref_path.exists():
        pytest.skip("data/profile.json not present — comparison skipped")
    raw = json.loads(ref_path.read_text(encoding="utf-8"))
    # ... rest unchanged
```

### IN-07: ResumeUploader error precedence hides server retries

**File:** `frontend/src/components/profile/ResumeUploader.tsx:182-189`
**Issue:** "client-side validation takes precedence over server-side error" is implemented as `clientError ? ... : isError ? describeError(error) : null`. When `clientError` is set, retrying the upload after the user fixes the file still won't clear the server-side error display from the previous attempt because clientError will be cleared and `isError` from the *prior* mutation may still be truthy until the next `mutate()` call. Not catastrophic, but the user sees the old error briefly. Minor UX nit.
**Fix:** Either reset the mutation on file change (`upload.reset()` in `handleCandidate`) or hide the server error when a new valid file is staged.

### IN-08: Sonner toast referenced in code-comments but no Sonner imports

**File:** `frontend/src/components/profile/types.ts:46`, `frontend/src/components/profile/useResumeUpload.ts:8-13` (comment), `frontend/src/components/profile/useResumeUpload.test.tsx:9` (comment in header — "toast + cache invalidate")
**Issue:** Documentation comments in three places reference a "Sonner toast" but no file imports from `sonner` or wires a `<Toaster />`. Either docs are stale (toast deferred) or a wiring step was skipped. Worth a one-line `// TODO(phase-7-deferred): wire Sonner toast` in the hook, or scrub the references.
**Fix:** If toast is deferred to a later wave, mark explicitly. Otherwise wire per WR-05 fix.

---

_Reviewed: 2026-05-28T13:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
