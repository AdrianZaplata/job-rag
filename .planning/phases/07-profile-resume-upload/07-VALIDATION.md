---
phase: 7
slug: profile-resume-upload
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Seeded from 07-RESEARCH.md §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 9.x + pytest-asyncio |
| **Framework (frontend)** | vitest + @testing-library/react |
| **Config file (backend)** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Config file (frontend)** | `frontend/vitest.config.ts` |
| **Quick run command (backend)** | `uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x` |
| **Quick run command (frontend)** | `cd frontend && npm test -- --run --reporter=verbose profile/` |
| **Full suite command (backend)** | `uv run pytest` |
| **Full suite command (frontend)** | `cd frontend && npm test -- --run` |
| **Static checks** | `uv run ruff check src/ tests/` + `uv run pyright src/` + `cd frontend && npm run typecheck` |
| **Estimated runtime** | ~45 s backend + ~30 s frontend (Phase 7 adds ~20 tests; existing suite ~250 tests) |

---

## Sampling Rate

- **After every task commit:** Run the matching focused command (pytest `-k <task-keyword>` or `vitest <component>`)
- **After every plan wave:** Run quick run command for the wave's domain (backend or frontend)
- **Before `/gsd-verify-work`:** Full suite (both backend and frontend) + static checks must be green
- **Max feedback latency:** 60 seconds (single test) / 120 seconds (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 0 | PROF-02 | T-07-02 | pypdf/python-docx deps pinned to safe versions | static | `grep -E "pypdf|python-docx" pyproject.toml` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 0 | PROF-02 | — | settings.max_resume_size_bytes default = 2_000_000 | static | `uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000"` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 0 | PROF-02..06 | — | test fixtures committed | static | `test -f tests/fixtures/sample-resume.pdf -a -f tests/fixtures/sample-resume.docx -a -f tests/fixtures/encrypted-sample.pdf -a -f tests/fixtures/empty-text-sample.pdf` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | PROF-01 | T-07-01 | load_profile is async, reads user_profile table | unit | `uv run pytest tests/test_matching.py -k load_profile_returns_seeded_row` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | PROF-01 | — | RuntimeError when row missing | unit | `uv run pytest tests/test_matching.py -k load_profile_fails_when_row_missing` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 1 | PROF-01 | — | filesystem-independent (no profile.json read) | unit | `uv run pytest tests/test_matching.py -k load_profile_independent_of_filesystem` | ❌ W0 | ⬜ pending |
| 07-02-04 | 02 | 1 | PROF-01 | — | grep proof: no production read of profile.json | static | `! grep -rn "profile.json" src/ \| grep -v README` | ✅ | ⬜ pending |
| 07-02-05 | 02 | 1 | PROF-01 | — | call-site flip: /match, /gaps, analytics, MCP tools | integration | `uv run pytest tests/test_api.py tests/test_analytics.py tests/test_mcp_server.py -k "match or gaps or skill_gaps or cv_vs_market"` | ✅ | ⬜ pending |
| 07-02-06 | 02 | 1 | PROF-01 | T-07-03 | alembic seed migration idempotent UPSERT | migration | `uv run pytest tests/test_alembic.py -k seed_user_profile` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 1 | PROF-03 | T-07-04 | RESUME_PROMPT_VERSION constant + system prompt module | static | `uv run python -c "from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT; assert RESUME_PROMPT_VERSION == '1.0'"` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 1 | PROF-03 | — | REJECTED_SOFT_SKILLS reused in resume prompt | static | `grep REJECTED_SOFT_SKILLS src/job_rag/extraction/resume_prompt.py` | ❌ W0 | ⬜ pending |
| 07-03-03 | 03 | 1 | PROF-03 | — | ResumeExtraction Pydantic model w/ 6 fields per D-13 | static | `uv run python -c "from job_rag.models import ResumeExtraction; m = ResumeExtraction.model_json_schema(); assert {'skills','target_roles','preferred_locations','min_salary_eur','remote_preference','years_experience'} <= m['properties'].keys()"` | ❌ W0 | ⬜ pending |
| 07-03-04 | 03 | 1 | PROF-03 | — | extract_resume returns ResumeExtraction | unit | `uv run pytest tests/test_resume_extractor.py -k structured_output` | ❌ W0 | ⬜ pending |
| 07-03-05 | 03 | 1 | PROF-03 | — | tenacity retries 3x then raises | unit | `uv run pytest tests/test_resume_extractor.py -k retries_3x` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 2 | PROF-02 | T-07-02 | 413 BEFORE body read (Content-Length header guard) | integration | `uv run pytest tests/test_profile.py -k 413_oversized_content_length` | ❌ W0 | ⬜ pending |
| 07-04-02 | 04 | 2 | PROF-02 | T-07-02 | 413 on chunked-encoding fallback | integration | `uv run pytest tests/test_profile.py -k 413_chunked_streaming` | ❌ W0 | ⬜ pending |
| 07-04-03 | 04 | 2 | PROF-02 | T-07-05 | 415 unsupported file types rejected | integration | `uv run pytest tests/test_profile.py -k 415_txt_file_rejected` | ❌ W0 | ⬜ pending |
| 07-04-04 | 04 | 2 | PROF-02 | — | 422 encrypted PDF | integration | `uv run pytest tests/test_profile.py -k 422_encrypted_pdf` | ❌ W0 | ⬜ pending |
| 07-04-05 | 04 | 2 | PROF-02 | — | 422 empty-text PDF (< 100 chars) | integration | `uv run pytest tests/test_profile.py -k 422_empty_text_pdf` | ❌ W0 | ⬜ pending |
| 07-04-06 | 04 | 2 | PROF-03 | — | 422 extraction failed after 3 retries | integration | `uv run pytest tests/test_profile.py -k 422_extraction_failed` | ❌ W0 | ⬜ pending |
| 07-04-07 | 04 | 2 | PROF-02, PROF-04 | — | happy path: PDF → diff present | integration | `uv run pytest tests/test_profile.py -k upload_pdf_happy_path` | ❌ W0 | ⬜ pending |
| 07-04-08 | 04 | 2 | PROF-02, PROF-04 | — | happy path: DOCX → diff present | integration | `uv run pytest tests/test_profile.py -k upload_docx_happy_path` | ❌ W0 | ⬜ pending |
| 07-04-09 | 04 | 2 | PROF-04 | — | compute_skills_diff classifies correctly | unit | `uv run pytest tests/test_profile.py -k compute_skills_diff_classifies` | ❌ W0 | ⬜ pending |
| 07-04-10 | 04 | 2 | PROF-04 | — | diff ordering: added → removed → unchanged | unit | `uv run pytest tests/test_profile.py -k compute_skills_diff_orders` | ❌ W0 | ⬜ pending |
| 07-04-11 | 04 | 2 | PROF-04 | — | diff normalises via _normalize_skill | unit | `uv run pytest tests/test_profile.py -k compute_skills_diff_normalizes` | ❌ W0 | ⬜ pending |
| 07-04-12 | 04 | 2 | PROF-06 | T-07-06 | PATCH replaces skills_json | integration | `uv run pytest tests/test_profile.py -k patch_replaces_skills_json` | ❌ W0 | ⬜ pending |
| 07-04-13 | 04 | 2 | PROF-06 | — | PATCH None fields preserve existing | integration | `uv run pytest tests/test_profile.py -k patch_none_fields_preserve` | ❌ W0 | ⬜ pending |
| 07-04-14 | 04 | 2 | PROF-06 | — | PATCH returns loaded profile | integration | `uv run pytest tests/test_profile.py -k patch_returns_loaded_profile` | ❌ W0 | ⬜ pending |
| 07-04-15 | 04 | 2 | PROF-06 | T-07-07 | Langfuse trace has 4 spans | unit | `uv run pytest tests/test_observability.py -k resume_upload_trace_has_four_spans` | ❌ W0 | ⬜ pending |
| 07-04-16 | 04 | 2 | PROF-06 | T-07-08 | Langfuse trace does NOT capture raw resume text (PII) | unit | `uv run pytest tests/test_observability.py -k resume_trace_does_not_capture_text` | ❌ W0 | ⬜ pending |
| 07-04-17 | 04 | 2 | PROF-06 | — | Langfuse fail-open when keys missing | unit | `uv run pytest tests/test_observability.py -k langfuse_fail_open_when_keys_missing` | ❌ W0 | ⬜ pending |
| 07-05-01 | 05 | 3 | PROF-05 | — | OpenAPI snapshot regenerated | static | `cd frontend && npm run codegen:snapshot && git diff --exit-code openapi.snapshot.json` | ✅ | ⬜ pending |
| 07-05-02 | 05 | 3 | PROF-05 | — | components/profile/ directory has 6 files per D-29 | static | `test $(ls frontend/src/components/profile/*.{ts,tsx} 2>/dev/null \| wc -l) -ge 6` | ❌ W0 | ⬜ pending |
| 07-05-03 | 05 | 3 | PROF-05 | — | profile.ts exports uploadResume + saveProfile | static | `grep -E "export.*(uploadResume\|saveProfile)" frontend/src/api/profile.ts` | ❌ W0 | ⬜ pending |
| 07-05-04 | 05 | 3 | PROF-05 | — | Profile.tsx no longer renders PhasePlaceholder | static | `! grep PhasePlaceholder frontend/src/routes/Profile.tsx` | ❌ W0 | ⬜ pending |
| 07-05-05 | 05 | 3 | PROF-05 | — | ProfileView renders read-only chips when profile loaded | vitest | `cd frontend && npm test -- --run ProfileView` | ❌ W0 | ⬜ pending |
| 07-05-06 | 05 | 3 | PROF-02, PROF-05 | T-07-02 | ResumeUploader client-side pre-checks (.pdf/.docx, ≤2 MB) | vitest | `cd frontend && npm test -- --run ResumeUploader` | ❌ W0 | ⬜ pending |
| 07-05-07 | 05 | 3 | PROF-05 | — | SkillDiffChip status pill + Pencil + Enter/Esc edit | vitest | `cd frontend && npm test -- --run SkillDiffChip` | ❌ W0 | ⬜ pending |
| 07-05-08 | 05 | 3 | PROF-05 | — | ReviewPanel sticky footer + live summary | vitest | `cd frontend && npm test -- --run ReviewPanel` | ❌ W0 | ⬜ pending |
| 07-05-09 | 05 | 3 | PROF-05, PROF-06 | — | useResumeUpload state machine + cache invalidation | vitest | `cd frontend && npm test -- --run useResumeUpload` | ❌ W0 | ⬜ pending |
| 07-05-10 | 05 | 3 | PROF-05 | — | typecheck passes | static | `cd frontend && npm run typecheck` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*File Exists: ✅ = existing test file present · ❌ W0 = Wave-0 task creates the file*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — add `pypdf>=6,<7` and `python-docx>=1,<2` to `[project] dependencies`; `uv lock` updates `uv.lock`
- [ ] `src/job_rag/config.py` — add `max_resume_size_bytes: int = 2_000_000` Settings field
- [ ] `tests/fixtures/sample-resume.pdf` — synthetic ~50 KB PDF with mock skills (committed)
- [ ] `tests/fixtures/sample-resume.docx` — synthetic DOCX (committed)
- [ ] `tests/fixtures/encrypted-sample.pdf` — synthetic encrypted PDF (committed)
- [ ] `tests/fixtures/empty-text-sample.pdf` — synthetic image-only PDF (committed)
- [ ] `tests/conftest.py` — fixtures `sample_resume_pdf`, `sample_resume_docx`, `encrypted_resume_pdf`, `empty_text_resume_pdf` reading the files above
- [ ] `tests/test_profile.py` — empty file with module docstring (Wave-1+2 fills tests)
- [ ] `tests/test_resume_extractor.py` — empty file with module docstring
- [ ] `tests/test_observability.py` — append resume-trace test fixtures (file may already exist)
- [ ] `tests/test_alembic.py` (NEW or appended) — fixture for seed migration round-trip
- [ ] `frontend/src/components/profile/` — directory created (Wave-3 fills components)
- [ ] `data/README.md` — NEW; documents the file's role as "reference snapshot, NOT runtime read path" per D-04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Oversized upload aborts at headers stage (no body bytes transmitted) | PROF-02 | DevTools observation — can't be reliably asserted from inside the server in an integration test | 1. Open `/profile` in dev. 2. Open DevTools Network tab. 3. Drop a 5 MB PDF. 4. Observe request: status 413, body transmitted bytes ≈ 0 (only headers reached the server). |
| Langfuse trace shows single `resume_upload` trace with 4 spans | PROF-06 | Requires staging environment with Langfuse keys set | 1. Set `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` in staging. 2. Upload a resume, then save. 3. Open Langfuse dashboard. 4. Find the `resume_upload` trace by `extraction_id`. 5. Confirm 4 spans present: `text_extract`, `llm_extract`, `diff_compute`, `profile_save`. |
| Dashboard CV-vs-market score reflects new skills post-save | PROF-06 | UX outcome — verifies the cache invalidation works end-to-end | 1. Upload + save adding 2 new skills. 2. Navigate to `/dashboard`. 3. Observe CV-vs-market widget shows the new skills counted in the match. |
| Inline edit on added chip persists through save | PROF-05 | Visual + semantic outcome | 1. Upload a resume. 2. Click Pencil on an added chip; rename it. 3. Press Enter. 4. Click Save. 5. Refresh `/profile`; the renamed skill appears in the current-skills list. |
| Cold-start awareness copy steps appear | PROF-05 | Time-sensitive UX | 1. Trigger cold start (scale-to-zero idle for ~5 min on Azure). 2. Upload resume. 3. Observe status copy transition: `Reading your resume…` → `Asking the agent…` → `Still working — extraction can take a minute on first load…`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s (full suite) / 60s (single test)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
