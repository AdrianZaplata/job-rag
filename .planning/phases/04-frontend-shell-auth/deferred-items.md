# Phase 04 — Deferred Items

Items discovered during Phase 4 execution that fall OUTSIDE the active plan's
scope. Per SCOPE BOUNDARY rule: log here; do NOT fix during the current plan
unless the deferred item directly blocks current-task completion.

## From Plan 04-01 (Wave 0 foundation)

### Pre-existing test failure: `test_alembic.py::test_0004_{up,down}grade_smoke`

- **Discovered:** 2026-05-20 during Plan 04-01 GREEN verification.
- **Symptom:** `KeyError: 'DATABASE_URL'` raised inside both Alembic smoke
  tests when `pytest -m 'not eval'` is run from a shell that does NOT export
  `DATABASE_URL`. Confirmed pre-existing by reproducing the failure on `master`
  (HEAD before any Plan 04-01 changes) via `git stash && pytest tests/test_alembic.py`.
- **Root cause:** the tests reference `os.environ["DATABASE_URL"]` unconditionally
  rather than reusing the existing `_postgres_reachable()` skip-gate pattern.
- **Why deferred:** out of scope for Plan 04-01 (no code touched in `tests/test_alembic.py`
  nor in any Alembic migration). Phase 2 Plan 02-03 introduced these tests; Plan 04-04
  (the migration plan) is the natural place to widen the skip-gate.
- **Workaround:** export `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/job_rag`
  before running pytest locally; CI passes because the workflow seeds the env var.
- **Recommended fix (future plan):** mirror the `_postgres_reachable()` guard in the
  two failing tests — gate `command.upgrade(cfg, "0005")` calls behind both the
  reachability check AND a `DATABASE_URL` presence check.
