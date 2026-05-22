# Phase 05 Dashboard - Deferred Items

Out-of-scope discoveries during plan execution that were NOT auto-fixed (per executor scope-boundary rules).

## Pre-existing Test Failures

### 1. tests/test_alembic.py::test_0004_upgrade_smoke + test_0004_downgrade_smoke

- **Discovered during:** Plan 05-02 execution (verifying no regressions from analytics.py)
- **Failure:** `KeyError: 'DATABASE_URL'`
- **Status:** Pre-existing — reproduced after `git stash` of all 05-02 changes
- **Cause:** Tests require `DATABASE_URL` env var pointing at a real Postgres; the CI/dev environment didn't have it set during this run
- **Action:** Not addressed by Plan 05-02 (out of scope per the scope-boundary rule — failures in unrelated test files NOT caused by current task)
- **Owner:** Track via phase-level cleanup or wire `DATABASE_URL` default in `tests/conftest.py` if it becomes a blocker
