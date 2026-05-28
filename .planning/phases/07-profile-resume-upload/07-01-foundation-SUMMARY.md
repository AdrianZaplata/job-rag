---
phase: 07-profile-resume-upload
plan: 01
subsystem: testing
tags: [pypdf, python-docx, pytest, alembic, fixtures, settings]

# Dependency graph
requires:
  - phase: 01-backend-prep
    provides: "Field(default=..., ge=1) Settings pattern; tests/conftest.py file-bytes fixture shape; tests/fixtures/ directory established"
  - phase: 02-corpus-cleanup
    provides: "PROMPT_VERSION + REJECTED_SOFT_SKILLS conventions (Phase 7 Plan 03 will mirror)"
provides:
  - "pypdf>=6,<7 (resolved to 6.12.2) + python-docx>=1,<2 (resolved to 1.2.0) backend deps"
  - "settings.max_resume_size_bytes = 2_000_000 with ge=1 guard"
  - "Four synthetic resume fixtures under tests/fixtures/ committed as binaries"
  - "tests/conftest.py byte fixtures: sample_resume_pdf, sample_resume_docx, encrypted_resume_pdf, empty_text_resume_pdf"
  - "tests/test_profile.py + tests/test_resume_extractor.py empty scaffolds (importable)"
  - "tests/test_observability.py Phase 7 section-header comment (Plan 04 appends)"
  - "scripts/generate_resume_fixtures.py one-shot fixture regenerator (commits the script for reproducibility)"
  - "data/README.md repurposes data/profile.json as reference snapshot (NOT runtime read path)"
  - "frontend/src/components/profile/ directory committed via .gitkeep"
affects: [07-02-load-profile-flip, 07-03-resume-extractor, 07-04-upload-routes, 07-05-frontend-review-panel]

# Tech tracking
tech-stack:
  added: [pypdf 6.12.2, python-docx 1.2.0, lxml 6.1.1 (transitive)]
  patterns: [synthetic-fixture watermarking (T-07-foundation-PII mitigation), one-shot fixture regenerator scripts under scripts/, Wave-0 empty test scaffolds with module docstrings]

key-files:
  created:
    - data/README.md
    - tests/fixtures/sample-resume.pdf
    - tests/fixtures/sample-resume.docx
    - tests/fixtures/encrypted-sample.pdf
    - tests/fixtures/empty-text-sample.pdf
    - tests/test_profile.py
    - tests/test_resume_extractor.py
    - scripts/generate_resume_fixtures.py
    - frontend/src/components/profile/.gitkeep
  modified:
    - pyproject.toml
    - uv.lock
    - src/job_rag/config.py
    - tests/conftest.py
    - tests/test_observability.py

key-decisions:
  - "Generated synthetic PDFs via pypdf alone (no reportlab); built a minimal content stream with Helvetica /F1 Tf + Td + Tj ops so pypdf.PdfReader.extract_text() returns the original lines"
  - "Committed scripts/generate_resume_fixtures.py so fixtures are reproducible without storing the generation procedure only in commit messages"
  - "All four resume fixtures contain a 'TEST FIXTURE -- synthetic data' watermark (mitigates T-07-foundation-PII per CONTEXT Discretion line 288)"
  - "tests/test_alembic.py NOT modified -- already exists from Phase 1 plan 01-02 D-08 grep guard; Plan 02 will append the 0006_seed_user_profile round-trip test"

patterns-established:
  - "Pattern: Wave-0 fixture binaries committed under tests/fixtures/ alongside a regenerator script under scripts/ so the synthesis procedure stays in-tree"
  - "Pattern: empty test scaffolds with module docstrings stating which downstream plan fills them (allows pytest --collect-only to pass without ImportError before tests exist)"

requirements-completed: [PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06]

# Metrics
duration: ~8min
completed: 2026-05-28
---

# Phase 07 Plan 01: Foundation Summary

**pypdf 6.12.2 + python-docx 1.2.0 backend deps pinned, 2 MB upload Setting added, four synthetic watermarked resume fixtures + four conftest byte fixtures + two empty test scaffolds committed so Plans 02-05 can run their tests without yak-shaving infrastructure.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 3
- **Files modified/created:** 14

## Accomplishments

- Wave-0 backend deps landed (`pypdf>=6,<7` resolved to 6.12.2; `python-docx>=1,<2` resolved to 1.2.0). `uv.lock` updated; lxml 6.1.1 pulled in transitively.
- `settings.max_resume_size_bytes` Setting wired (default 2_000_000, `ge=1` guard mirrors `agent_timeout_seconds`). Plan 04 will consume this from the new `ResumeUploadSizeGuard` ASGI middleware to enforce the 413-before-body-read contract.
- Four synthetic resume fixtures committed as binaries under `tests/fixtures/`. All contain a "TEST FIXTURE -- synthetic data" watermark; none contain any fragment of Adrian's real resume content (T-07-foundation-PII mitigation per CONTEXT Discretion line 288).
- Four matching byte fixtures appended to `tests/conftest.py` (`sample_resume_pdf`, `sample_resume_docx`, `encrypted_resume_pdf`, `empty_text_resume_pdf`) following the existing `sample_raw_text` file-read fixture shape.
- Two empty test scaffolds with module docstrings (`tests/test_profile.py`, `tests/test_resume_extractor.py`) so pytest can `--collect-only` without ImportError before downstream plans add tests.
- `tests/test_observability.py` got a Phase 7 section-header comment under the existing TestFlush block; Plan 04 appends the resume_upload trace tests there.
- `frontend/src/components/profile/` directory committed via `.gitkeep` so Plan 05 can drop ProfileView / ResumeUploader / ReviewPanel / SkillDiffChip / useResumeUpload / types into a tracked directory immediately.
- `data/README.md` (NEW, 9 lines) records `data/profile.json`'s repurposed role as a reference snapshot, NOT a runtime read path. Resolves the D-04 contract before Plan 02's seed migration lands.

## Task Commits

1. **Task 1: Deps + Setting + data/README.md** — `87a44ee` (feat)
2. **Task 2: Synthetic resume fixtures + regenerator script** — `a3fb818` (feat)
3. **Task 3: conftest byte fixtures + test scaffolds + frontend profile/ dir** — `f258c55` (test)

## Files Created/Modified

Created:
- `data/README.md` — repurposes `data/profile.json` as reference snapshot per D-04
- `scripts/generate_resume_fixtures.py` — one-shot fixture regenerator using pypdf + python-docx
- `tests/fixtures/sample-resume.pdf` — 1006 bytes; pypdf extracts 238 chars including "TEST FIXTURE" watermark
- `tests/fixtures/sample-resume.docx` — 36911 bytes; paragraphs + 2x2 table; watermark present
- `tests/fixtures/encrypted-sample.pdf` — 826 bytes; `PdfReader.is_encrypted == True` (user_password='test')
- `tests/fixtures/empty-text-sample.pdf` — 431 bytes; blank page; extracts 0 chars (<100 threshold)
- `tests/test_profile.py` — empty scaffold; Plans 02+04 fill
- `tests/test_resume_extractor.py` — empty scaffold; Plan 03 fills
- `frontend/src/components/profile/.gitkeep` — directory marker; Plan 05 fills

Modified:
- `pyproject.toml` — added `pypdf>=6,<7` + `python-docx>=1,<2` to `[project] dependencies` (alphabetical neighbours of `python-multipart`)
- `uv.lock` — regenerated via `uv lock`; pypdf 6.12.2, python-docx 1.2.0, lxml 6.1.1 added
- `src/job_rag/config.py` — added `max_resume_size_bytes: int = Field(default=2_000_000, ge=1)` Setting next to `agent_timeout_seconds`
- `tests/conftest.py` — appended 4 byte fixtures after the existing `sample_raw_text` fixture
- `tests/test_observability.py` — appended Phase 7 section-header comment under TestFlush (Plan 04 will append actual tests below)

## Decisions Made

- **PDF generation strategy.** Built a minimal Helvetica content stream by hand using pypdf's low-level objects (`DecodedStreamObject` + `Tf`/`Td`/`Tj` operators) so the project does not pick up a `reportlab` runtime/dev dep just to generate two test PDFs. The script verifies the output by round-tripping `PdfReader.extract_text()` and asserting the original lines come back.
- **Regenerator committed.** `scripts/generate_resume_fixtures.py` is committed (not just executed and discarded) so the fixture synthesis procedure stays in-tree. This means a future maintainer can re-derive the binaries from source; the binaries themselves are intentionally version-controlled because pypdf timestamps make every regenerate produce a different byte sequence.
- **`tests/test_alembic.py` not modified.** The file already exists from Phase 1 plan 01-02 D-08 grep-guard tests. Per Plan 07-01 Task 3 step 5 ("If exists: skip — Plan 02 appends"), the file was left alone. Plan 02's seed migration round-trip test will append below the existing `0005_upgrade_smoke` block. Verified by `uv run pytest --collect-only tests/test_alembic.py` -> 6 tests collected (the pre-existing Phase 4 0005 tests).
- **`data/profile.json` not deleted.** Per D-04, the file stays as a reference snapshot and the `data/README.md` explicitly documents this contract. Plan 02 will assert via grep that production code (`src/`) never reads `profile.json` except through the new DB read path.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `<action>` for Task 2 listed two PDF-generation paths ("Use `pypdf` or `reportlab` (if available)"). The executor chose pypdf-only to keep the dev-dep surface unchanged; this is within the documented option set, not a deviation. The resulting fixtures pass every acceptance criterion in the plan verbatim.

## Issues Encountered

None. Each task verified green on first run.

## User Setup Required

None - no external service configuration required. The new `pypdf` + `python-docx` deps are public PyPI packages; `uv lock` resolved them without authentication or registry config changes.

## Next Phase Readiness

Wave-0 is complete. Every downstream Phase 7 plan can now:
- Import `pypdf` / `python-docx` without `uv add` first (Plans 03, 04)
- Read `settings.max_resume_size_bytes` from the existing Settings instance (Plan 04 middleware)
- Use the 4 conftest byte fixtures in upload integration tests (Plan 04)
- Write to `tests/test_profile.py` / `tests/test_resume_extractor.py` without creating the files (Plans 02, 03, 04)
- Drop components into `frontend/src/components/profile/` against a tracked directory (Plan 05)
- Append the seed migration round-trip test to the existing `tests/test_alembic.py` (Plan 02)

Blockers: None. Plan 02 can start immediately.

## Self-Check: PASSED

Verified after writing this SUMMARY.md:

Files exist (each command exit 0):
- `test -f pyproject.toml` -> FOUND
- `test -f uv.lock` -> FOUND
- `test -f src/job_rag/config.py` -> FOUND
- `test -f data/README.md` -> FOUND
- `test -f tests/fixtures/sample-resume.pdf` -> FOUND (1006 bytes)
- `test -f tests/fixtures/sample-resume.docx` -> FOUND (36911 bytes)
- `test -f tests/fixtures/encrypted-sample.pdf` -> FOUND (826 bytes)
- `test -f tests/fixtures/empty-text-sample.pdf` -> FOUND (431 bytes)
- `test -f tests/test_profile.py` -> FOUND
- `test -f tests/test_resume_extractor.py` -> FOUND
- `test -f tests/test_observability.py` -> FOUND
- `test -f tests/conftest.py` -> FOUND
- `test -f scripts/generate_resume_fixtures.py` -> FOUND
- `test -d frontend/src/components/profile` -> FOUND

Commits exist (verified via `git log --oneline`):
- `87a44ee` -> FOUND ("feat(07-01): add pypdf/python-docx deps + max_resume_size_bytes Setting + data/README.md")
- `a3fb818` -> FOUND ("feat(07-01): add four synthetic resume fixtures + regenerator script")
- `f258c55` -> FOUND ("test(07-01): add resume conftest fixtures + Wave-0 test scaffolds + profile/ dir")

Functional checks:
- `uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000"` -> PASSED
- `uv run pyright src/` -> 0 errors, 0 warnings
- `uv run pytest tests/test_matching.py tests/test_models.py tests/test_observability.py -x` -> 53 passed
- `uv run pytest --collect-only tests/test_profile.py tests/test_resume_extractor.py tests/test_alembic.py` -> exits clean, collects 6 pre-existing alembic tests
- Each fixture asserted: sample PDF extracts 238 chars (>=100), encrypted PDF `is_encrypted` is True, empty-text PDF extracts 0 chars (<100), DOCX contains "TEST FIXTURE" paragraph

---
*Phase: 07-profile-resume-upload*
*Plan: 01-foundation*
*Completed: 2026-05-28*
