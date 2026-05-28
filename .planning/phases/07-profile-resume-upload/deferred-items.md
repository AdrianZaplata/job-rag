# Phase 7 — Deferred Items

Issues discovered during Phase 7 execution that are out of scope for the
current plan but should be addressed in a follow-up phase.

## Discovered during Plan 07-02 (load-profile-flip)

### Pre-existing test failure: `test_0005_upgrade_populates_oid_when_env_set`

- **File:** `tests/test_alembic.py:292-335`
- **Symptom:** `AssertionError: assert None == 'test-oid-xyz-123'`
- **Root cause:** The test was written against the original 0005 migration
  body, which included an `UPDATE users SET entra_oid = ...` block keyed off
  the `SEEDED_USER_ENTRA_OID` env var. Phase 04.1 fix #1 moved that UPDATE
  out of the migration and into `src/job_rag/db/engine.py::_seed_entra_oid()`
  (so it re-runs on every container boot, not just once per revision-marker).
  The 0005 migration upgrade body is now schema-only — it adds the column +
  partial index but does NOT touch the seeded row. The test assertion that
  `entra_oid == 'test-oid-xyz-123'` after `command.upgrade(cfg, "0005")` is
  no longer valid; the env-driven UPDATE only fires via `_seed_entra_oid()`,
  which is called from `init_db()` not from `alembic upgrade` directly.
- **Verified pre-existing:** confirmed with `git stash` + isolated rerun
  during Plan 07-02 execution — failure reproduces without any Phase 7 code.
- **Recommendation:** Either delete the test (the env-set UPDATE flow is now
  covered by an engine-level test in Phase 04.1) OR rewrite it to invoke
  `_seed_entra_oid()` directly after the upgrade. Defer to Phase 8 docs/eval
  housekeeping or a Phase 04.2 follow-up.

This failure existed before Plan 07-02 started and is OUT OF SCOPE per the
GSD executor SCOPE BOUNDARY rule. Plan 07-02 did not modify
`tests/test_alembic.py::test_0005_upgrade_populates_oid_when_env_set`, the
0005 migration, or the engine `_seed_entra_oid()` helper.
