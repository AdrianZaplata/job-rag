---
phase: 07-profile-resume-upload
plan: 02
subsystem: backend
tags: [load_profile, alembic-seed, async, asyncpg, pgvector, user_profile, prof-01]

# Dependency graph
requires:
  - phase: 01-backend-prep
    provides: "load_profile() kwarg-only signature (D-07 forward hook); UserProfileDB table (D-12); SEEDED_USER_ID Python constant (D-08); init_db() wraps alembic upgrade head (D-04)"
  - phase: 04-frontend-shell-auth
    provides: "0005_adopt_entra_oid migration as current head; chained predecessor for 0006"
  - phase: 05-dashboard
    provides: "services/analytics.py::cv_match calls load_profile(user_id=...) — Phase 5 D-06 deliberately deferred the async flip to Phase 7"
provides:
  - "async def load_profile(session: AsyncSession, *, user_id: UUID | None = None) -> UserSkillProfile"
  - "alembic/versions/0006_seed_user_profile.py — idempotent UPSERT of Adrian's profile row via ON CONFLICT DO NOTHING"
  - "PROF-01 closed: no production read path for data/profile.json remains in src/"
  - "tests/conftest.py::db_session — fresh-engine per-test AsyncSession fixture (avoids cross-loop asyncpg errors)"
affects: [07-03-resume-extractor, 07-04-upload-routes-diff-langfuse]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "alembic data-only seed migration via embedded Python dict literal + ON CONFLICT (user_id) DO NOTHING (idempotent T-07-03 mitigation)"
    - "per-test fresh async engine in pytest fixture to sidestep `Future ... attached to a different loop` from asyncpg pool reuse"

key-files:
  created:
    - alembic/versions/0006_seed_user_profile.py
    - .planning/phases/07-profile-resume-upload/deferred-items.md
  modified:
    - src/job_rag/services/matching.py
    - src/job_rag/api/routes.py
    - src/job_rag/services/analytics.py
    - src/job_rag/mcp_server/tools.py
    - src/job_rag/config.py
    - src/job_rag/db/models.py
    - tests/test_matching.py
    - tests/test_alembic.py
    - tests/test_analytics.py
    - tests/test_mcp_server.py
    - tests/conftest.py

key-decisions:
  - "Kept the body-flip exact-shape preserving — UserSkillProfile return value byte-equivalent to the Phase 1 JSON read for the seeded row; this is what makes the flip transparent to Phase 5's CV-vs-market widget"
  - "Embedded data/profile.json as a Python dict literal in the migration rather than reading it at runtime — data/ is gitignored at the container layer; a runtime file read would crash on fresh ACA boot per D-04"
  - "Removed settings.profile_path entirely (was a Phase 1 D-07 forward-compat hint; now genuinely unused). Rewrote test_load_profile_independent_of_filesystem to chdir into an empty tmp_path so the filesystem-independence assertion no longer hinges on a no-longer-existent setting"
  - "Per-test fresh async engine in conftest.db_session — module-global AsyncSessionLocal caches asyncpg connections to the loop they were opened on, so pytest-asyncio's per-test loop scope causes `Future ... attached to a different loop` errors. The fresh-engine fixture is slower (engine spin-up per test) but reliable; the slowdown is invisible at our test volume (3 tests, ~0.3s total)"

requirements-completed: [PROF-01]

# Metrics
duration: ~10 min
completed: 2026-05-28
---

# Phase 07 Plan 02: load-profile-flip Summary

**`load_profile()` flipped to an async DB query against `user_profile` (PROF-01); 5 call sites + 2 mock test files updated in lockstep; new `0006_seed_user_profile` Alembic migration idempotently seeds Adrian's row from an embedded dict literal; `data/profile.json` no longer reachable from any production code path under `src/`.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 2 (TDD RED + GREEN cycle on Task 1, then Task 2 mechanical fan-out)
- **Files modified/created:** 13 (2 new + 11 modified)
- **Lines changed:** +548 / −49 across 3 commits

## Accomplishments

- **PROF-01 closed.** `load_profile()` now reads from the `user_profile` DB row keyed on `user_id`. `data/profile.json` survives in the repo as a reference snapshot (D-04) but is not part of any runtime read path.
- **0006 seed migration landed.** `alembic/versions/0006_seed_user_profile.py` (142 lines) embeds the full 62-skill profile + target_roles + preferred_locations + min_salary_eur + remote_preference as a Python dict literal and INSERTs it via `ON CONFLICT (user_id) DO NOTHING`. Idempotent against PG16 prod + PG17 dev; downgrade deletes ONLY the seeded UUID row (verified by `test_0006_seed_user_profile_downgrade_deletes_only_seeded_row`).
- **`load_profile()` body-flipped.** New signature: `async def load_profile(session: AsyncSession, *, user_id: UUID | None = None) -> UserSkillProfile`. Implementation: parameter-bound `select().where()` (T-07-01 SQLi mitigation), Pydantic-validated reconstitution from JSON columns, explicit `RuntimeError` on missing row (data-integrity bug, not user error — see SUMMARY decisions). Net: −23 lines old body + +42 lines new body = +19 lines including expanded docstring.
- **5 call sites flipped.** Each now uses `await load_profile(session, user_id=...)` with the session already in scope:
  - `src/job_rag/api/routes.py:194` (`/match` handler) — `session` is `Annotated[AsyncSession, Depends(get_session)]`
  - `src/job_rag/api/routes.py:219` (`/gaps` handler) — same
  - `src/job_rag/services/analytics.py:296` (`_compute_cv_vs_market` / dashboard CV-vs-market widget) — takes `session: AsyncSession` parameter from caller
  - `src/job_rag/mcp_server/tools.py:123` (`match_skills`) — reuses the `async with AsyncSessionLocal() as session:` session already open inside the tool
  - `src/job_rag/mcp_server/tools.py:150` (`skill_gaps`) — same
- **2 mock test files updated.** `tests/test_mcp_server.py` (2 sites) switched to `patch(..., new_callable=AsyncMock)` so the awaited mock returns a coroutine. `tests/test_analytics.py` (4 sites) replaced `lambda *, user_id: ...` synchronous monkeypatches with `async def _fake_load_profile(session, *, user_id=None): return ...` matching the new signature.
- **New `db_session` async fixture.** `tests/conftest.py` adds a per-test fresh-async-engine fixture (skips when PG unreachable). The fresh-engine pattern sidesteps asyncpg's loop-caching: the module-global `AsyncSessionLocal` caches connections to the first event loop they were opened on, which collides with pytest-asyncio's default per-test loop scope.
- **Grep guards green.** `grep -rn "profile.json" src/` returns 0 matches. `grep -rn "load_profile" src/` shows every caller uses `await load_profile(session, ...)` and every match outside production code is a docstring or import line.

## Task Commits

1. **Task 1 RED — 0006 migration + failing tests** — `0163664` (test): seeded migration applied locally, three test_matching tests added (referencing the not-yet-existing async signature), three test_alembic tests added (round-trip + idempotency + scoped-downgrade), db_session conftest fixture added.
2. **Task 1 GREEN — load_profile body flip** — `d02ef78` (feat): async DB query body, signature change, dropped `path` kwarg, conftest fixture refined to fresh-engine-per-test.
3. **Task 2 — 5 call sites + 2 mock files + grep guard cleanup** — `1e06ba1` (feat): every caller awaits load_profile(session, …); 2 test_mcp_server patches → AsyncMock; 4 test_analytics monkeypatches → async def; profile_path Setting removed; literal "profile.json" stripped from docstrings; test 3 rewritten to chdir into empty tmp_path.

## Files Created/Modified

Created:
- `alembic/versions/0006_seed_user_profile.py` (142 lines) — seed migration; embedded `_PROFILE` dict literal from `data/profile.json` snapshot as of 2026-05-28; idempotent UPSERT; symmetric downgrade
- `.planning/phases/07-profile-resume-upload/deferred-items.md` — logs the pre-existing `test_0005_upgrade_populates_oid_when_env_set` failure (Phase 04.1 deviation #3 left it stale)

Modified:
- `src/job_rag/services/matching.py` — `load_profile()` body-flip + signature change; removed `Path`/`profile_path` references; added imports for `select`, `AsyncSession`, `UserProfileDB`, `RemotePolicy`, `UserSkill`
- `src/job_rag/api/routes.py` — 2 call sites flipped (`/match`, `/gaps`); module docstring updated to reflect the await pattern
- `src/job_rag/services/analytics.py` — 1 call site flipped (`_compute_cv_vs_market`)
- `src/job_rag/mcp_server/tools.py` — 2 call sites flipped (`match_skills`, `skill_gaps`); both reuse the AsyncSessionLocal session already open in the enclosing `async with` block
- `src/job_rag/config.py` — removed `profile_path` Setting field; replaced with explanatory comment describing the Phase 7 D-01..D-05 removal
- `src/job_rag/db/models.py` — UserProfileDB docstring rewritten (no literal "profile.json")
- `tests/test_matching.py` — 3 new tests: `test_load_profile_returns_seeded_row`, `test_load_profile_fails_when_row_missing`, `test_load_profile_independent_of_filesystem`
- `tests/test_alembic.py` — 3 new tests: `test_0006_seed_user_profile_inserts_row`, `test_0006_seed_user_profile_idempotent`, `test_0006_seed_user_profile_downgrade_deletes_only_seeded_row`
- `tests/test_analytics.py` — 4 monkeypatch sites converted to async stub functions
- `tests/test_mcp_server.py` — 2 `patch(...)` sites converted to `new_callable=AsyncMock`
- `tests/conftest.py` — new `db_session` async fixture (fresh engine per test + PG-reachability skip)

## Decisions Made

- **Body-flip preserves exact return shape.** The new DB-backed `load_profile()` returns a `UserSkillProfile` byte-equivalent to what the Phase 1 JSON-file read returned for the seeded row. This is what makes the flip transparent to Phase 5's CV-vs-market widget: no API contract change, no Phase 5 test regression. Verified via the 4 `cv_match` tests in `tests/test_analytics.py` still passing after the call-site flip + mock-async conversion.
- **Embed `_PROFILE` as a dict literal, do NOT read `data/profile.json` at runtime.** The seed migration must be runnable against a fresh container image where `data/` is gitignored at the container layer. A runtime `Path("data/profile.json").read_text()` inside the migration would crash on fresh ACA boot. The trade-off is that future seed-content changes require regenerating the literal in lockstep with `data/profile.json` (documented in the migration's module docstring).
- **Removed `settings.profile_path` entirely.** It was a Phase 1 D-07 forward-compat hint string and is no longer read by any production code. Keeping it would force the grep guard `grep -rn "profile.json" src/` to never reach 0 matches. The test `test_load_profile_independent_of_filesystem` was rewritten to chdir into an empty tmp_path — proving filesystem-independence by stronger means (no `data/` dir exists at all when the call is made, not just that a config string points to a nonexistent path).
- **Fresh async engine per test in `db_session` fixture.** SQLAlchemy's module-global `AsyncSessionLocal` (used by the FastAPI app) caches `asyncpg` connections to the event loop they were opened on. pytest-asyncio's default per-test loop scope means each test gets a fresh loop, but the cached connections still point at the previous loop — yielding `RuntimeError: Future ... attached to a different loop`. The fix: create a fresh engine inside the fixture, `await engine.dispose()` on teardown. Slower (engine spin-up per test) but reliable.
- **Pre-existing `0005` env-set test deferred.** `tests/test_alembic.py::test_0005_upgrade_populates_oid_when_env_set` fails on a clean Phase 7 baseline because Phase 04.1 fix #1 moved the env-driven `entra_oid` UPDATE out of the 0005 migration body and into `engine._seed_entra_oid()`. Verified pre-existing via `git stash` rerun; documented in `deferred-items.md` per the SCOPE BOUNDARY rule. The other six `test_alembic.py` tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Critical functionality] Removed `settings.profile_path` to satisfy the grep guard**
- **Found during:** Task 2 Step D verification
- **Issue:** The plan's grep guard `grep -rn "profile.json" src/` is meant to return 0 matches. Even after flipping `load_profile`'s body, three matches remained: a `profile_path` Setting default (`config.py:24`), a stale docstring in `db/models.py:119`, and a self-referential note in `matching.py:21`. While none of these were "production read paths" in the strict sense (Setting defaults aren't read; docstrings aren't read), the grep guard treats literal string presence as the signal.
- **Fix:** Removed the `profile_path` Setting field entirely; rewrote the two docstrings to avoid the literal "profile.json" string. Rewrote `test_load_profile_independent_of_filesystem` (which had monkeypatched `settings.profile_path`) to chdir into an empty `tmp_path` instead — a strictly stronger filesystem-independence assertion.
- **Files modified:** `src/job_rag/config.py`, `src/job_rag/db/models.py`, `src/job_rag/services/matching.py`, `tests/test_matching.py`
- **Commit:** `1e06ba1`

**2. [Rule 3 - Blocking] Cross-loop asyncpg errors in `db_session` fixture**
- **Found during:** Task 1 GREEN verification (first pytest run after body-flip)
- **Issue:** Initial `db_session` fixture reused the module-global `AsyncSessionLocal`. The first load_profile test passed; the second failed with `RuntimeError: Future ... attached to a different loop` because asyncpg connections cached to the first test's loop.
- **Fix:** Switched the fixture to create a fresh `create_async_engine(...)` per test and `await engine.dispose()` on teardown. Each test now opens connections inside its own loop.
- **Files modified:** `tests/conftest.py`
- **Commit:** `d02ef78` (folded into the GREEN body-flip commit since it was the same edit cycle)

**3. [Rule 1 - Bug] Bogus `pyright` error: 5 call sites failed during the GREEN body-flip commit**
- **Not a deviation per se** — this was the expected intermediate state between Task 1 and Task 2 (the body flip narrows the signature before the callers are updated). Documented in the Task 1 GREEN commit message so future archaeologists understand why pyright was momentarily red between commits `d02ef78` and `1e06ba1`.

## Issues Encountered

- **Initial CRLF line endings on `tests/test_matching.py`.** The Edit tool's append left CRLF line terminators (likely a tool-side normalization). Git's `.gitattributes` has `*.py text eol=lf` so the committed copy is LF, but the working tree warning appeared on `git add`. Normalized in-place with `tr -d '\r'`.
- **Pre-existing `0005` env-set test failure.** See decisions above and `deferred-items.md`. Cleanly out-of-scope per the SCOPE BOUNDARY rule.

## User Setup Required

None. The `0006_seed_user_profile` migration is applied automatically via `init_db()` on container boot (Phase 1 D-04). Local-dev runs the migration via the test runner's first-touch (verified during this plan execution by stopping at 0005, then upgrading to head).

## Next Plan Readiness

Plan 07-03 (resume extractor) and 07-04 (upload routes + diff + Langfuse) can now:
- Use the DB-backed `load_profile()` from `compute_skills_diff()` — the diff computation needs the current profile, and the new async signature is the call shape both plans expect (per CONTEXT D-17 / D-20).
- Trust that the `user_profile` row exists on any deployment that has run `alembic upgrade head` — the `RuntimeError` failure mode is reserved for genuine data-integrity bugs.
- Build PATCH `/profile` endpoints against the same async session pattern.

Blockers: None for Plan 07-03; the resume extractor module is independent of the DB read path.

## Self-Check: PASSED

Verified after writing this SUMMARY.md:

Files exist (each command exit 0):
- `test -f alembic/versions/0006_seed_user_profile.py` -> FOUND (142 lines)
- `test -f .planning/phases/07-profile-resume-upload/deferred-items.md` -> FOUND
- `test -f src/job_rag/services/matching.py` -> FOUND (176 lines; was 158)
- `test -f tests/test_matching.py` -> FOUND
- `test -f tests/test_alembic.py` -> FOUND
- `test -f tests/test_analytics.py` -> FOUND
- `test -f tests/test_mcp_server.py` -> FOUND
- `test -f tests/conftest.py` -> FOUND

Commits exist (verified via `git log --oneline`):
- `0163664` -> FOUND ("test(07-02): add 0006 seed migration + failing load_profile DB tests (RED)")
- `d02ef78` -> FOUND ("feat(07-02): flip load_profile() body to async DB query (PROF-01 / GREEN)")
- `1e06ba1` -> FOUND ("feat(07-02): flip 5 load_profile call sites + update 2 mock test files")

Functional checks:
- `grep -rn "profile.json" src/` -> exit 1 (0 matches) ✓
- `grep -E "async def load_profile" src/job_rag/services/matching.py` -> FOUND ✓
- `uv run alembic upgrade head` -> exit 0; second run no-op ✓
- `uv run alembic history` -> shows `0005 -> 0006 (head)` ✓
- `uv run pytest tests/test_matching.py -k load_profile -x` -> 3 passed ✓
- `uv run pytest tests/test_alembic.py -k seed_user_profile -x` -> 3 passed ✓
- `uv run pytest tests/test_api.py tests/test_analytics.py tests/test_mcp_server.py -k 'match or gaps or skill_gaps or cv_match'` -> 10 passed ✓
- `uv run pyright src/` -> 0 errors, 0 warnings, 0 informations ✓
- `uv run ruff check src/ tests/` -> All checks passed ✓
- `uv run pytest tests/ --deselect tests/test_alembic.py::test_0005_upgrade_populates_oid_when_env_set` -> 244 passed, 8 skipped (PG-skip-gated), 1 deselected (pre-existing) ✓

## TDD Gate Compliance

Plan 02 task 1 carried `tdd="true"`. Gate sequence in git log:
- `test(07-02): add 0006 seed migration + failing load_profile DB tests (RED)` — `0163664`
- `feat(07-02): flip load_profile() body to async DB query (PROF-01 / GREEN)` — `d02ef78`

RED→GREEN cycle observed; no REFACTOR commit needed.

---
*Phase: 07-profile-resume-upload*
*Plan: 02-profile-load-flip*
*Completed: 2026-05-28*
