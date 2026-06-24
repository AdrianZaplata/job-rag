---
phase: 07-profile-resume-upload
fixed_at: 2026-05-28T13:55:00Z
review_path: .planning/phases/07-profile-resume-upload/07-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-05-28T13:55:00Z
**Source review:** `.planning/phases/07-profile-resume-upload/07-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (Warnings only — Critical: 0; Info: 8 skipped per scope)
- Fixed: 5
- Skipped: 0

Backend suite: 262 passed, 8 skipped (1 pre-existing `test_alembic.py::test_0004_upgrade_smoke` `KeyError: 'DATABASE_URL'` skipped via `--ignore`; not introduced by these fixes).
Frontend suite: 113 passed across 22 files.

## Fixed Issues

### WR-01: `text` symbol shadowed by local variable in upload_resume

**Files modified:** `src/job_rag/api/routes.py`
**Commit:** 6db6cda
**Applied fix:** Renamed the local `text` (output of `_extract_pdf_text` / `_extract_docx_text`) to `resume_text` throughout `upload_resume`, including downstream `len()`, `.strip()`, `[:50_000]` truncation, the `extract_resume` call, and the Langfuse redaction payload at line 805. Module-level `from sqlalchemy import ... text ...` (used by the `/health` SQL probe at line 139) is no longer shadowed inside the upload handler. Verified with `pytest tests/test_profile.py` (14 passed).

### WR-02: ResumeUploader skeleton uses dynamic Tailwind classes

**Files modified:** `frontend/src/components/profile/ResumeUploader.tsx`
**Commit:** 2bd247a
**Applied fix:** Introduced a `SKELETON_WIDTHS` tuple of full-literal Tailwind classes (`w-16` / `w-20` / `w-24` / `w-28` — all core widths the v4 scanner emits) and swapped the inline `[20, 24, 16, 28, 20, 24, 18, 22].map(w => className={`h-6 w-${w}`})` for `SKELETON_WIDTHS.map(cls => className={`h-6 ${cls}`})`. The skeleton now renders all 8 bars at the intended widths regardless of v4's content-scanning. Verified with `vitest run src/components/profile/ResumeUploader.test.tsx` (7 passed).

### WR-03: compute_skills_diff loses canonical casing on unchanged rows

**Files modified:** `src/job_rag/services/profile.py`, `tests/test_profile.py`
**Commit:** 4424172
**Applied fix:** Changed `unchanged = sorted(extracted_map[k] ...)` to `unchanged = sorted(current_map[k] ...)` so the user's stored canonical casing wins when both sides normalize to the same key. Updated the function docstring to reflect the new invariant ("Casing: extracted casing for added rows; user casing for removed AND unchanged rows"). Updated `test_compute_skills_diff_normalizes_via_normalize_skill` to assert "Python" / "Fast-API" / "CI_CD" (current-side casing) in the unchanged bucket instead of the prior extracted-side casing. Verified with `pytest tests/test_profile.py` (14 passed).

### WR-04: SkillDiffChip commitEdit empty/no-op handling

**Files modified:** `frontend/src/components/profile/SkillDiffChip.tsx`
**Commit:** f70e9d1
**Applied fix:** Split the previously-conflated discard branch in `commitEdit`: empty input now delegates to `cancelEdit()` (preserving its semantics — also fires the existing `useEffect` re-sync path), while non-empty input commits only when `trimmed !== item.editedName`. Always call `setDraft(trimmed)` on close so re-opening the editor shows the last committed value rather than a stale draft. Verified with `vitest run src/components/profile/SkillDiffChip.test.tsx` (7 passed).

### WR-05: Profile route never exits 'saved'; toast not wired

**Files modified:** `frontend/src/components/profile/useResumeUpload.ts`, `frontend/src/components/profile/useResumeUpload.test.tsx`
**Commit:** 207108f
**Applied fix:** Imported `toast` from `sonner` (the `Toaster` component is already mounted at `AppShell.tsx:89`), fired `toast.success(`Saved ${profile.skills.length} skills to your profile`)` from the save mutation's `onSuccess`, and scheduled `setTimeout(() => setState({ phase: 'idle' }), 0)` so the `saved` phase is genuinely transient as documented in `types.ts:46-47`. Updated the matching unit test to (a) mock `sonner.toast`, (b) `await waitFor(...phase === 'idle')` instead of `'saved'`, and (c) assert `toast.success` was called with the skill-count message. Full frontend suite (113 tests across 22 files) passes.

---

_Fixed: 2026-05-28T13:55:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
