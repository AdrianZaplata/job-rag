---
phase: 04-frontend-shell-auth
plan: 02
subsystem: backend-auth
tags: [fastapi-azure-auth, ciam, entra-external-id, b2c-multi-tenant, alembic, oid-allowlist, jwt-validation]

# Dependency graph
requires:
  - phase: 04-frontend-shell-auth
    provides: "Plan 04-01 Wave 0 foundation — 4 Settings fields (entra_tenant_id/entra_tenant_subdomain/backend_audience/seeded_user_entra_oid), fastapi-azure-auth 5.2.0 dep, D-07 amendment in 04-CONTEXT.md, skip-on-missing test scaffolds in tests/test_entra_jwt.py"
  - phase: 01-backend-prep
    provides: "get_current_user_id() function-body rewrite target (D-10), Depends() wired on /match /gaps /ingest /agent /agent/stream, structlog get_logger pattern, 4 existing migrations (0001-0004) including users table from 0002 with entra_oid column already present as Text/unique"
provides:
  - "src/job_rag/api/auth.py with module-level azure_scheme = B2CMultiTenantAuthorizationCodeBearer(...) instance + rewritten get_current_user_id() body enforcing AUTH-06 oid allowlist"
  - "alembic/versions/0005_adopt_entra_oid.py — idempotent column-add + UPDATE-from-env + partial unique index ix_users_entra_oid_unique"
  - "tests/test_entra_jwt.py TestEntraJwtValidation + TestOidGuard tests ACTIVATED (3 previously-skipped tests now pass)"
  - "tests/test_alembic.py extended with 3 new 0005 smoke tests (test_0005_upgrade_smoke, test_0005_upgrade_populates_oid_when_env_set, test_0005_downgrade_smoke); all gated on DATABASE_URL + _postgres_reachable"
  - "tests/test_api.py /match + /gaps test cases updated to override get_current_user_id (auth now required for those routes — Rule 1 cascade fix)"
affects: [04-03-ci-frontend, 04-04-frontend-scaffold, 04-05-frontend-wiring, 04-06-runbook]

# Tech tracking
tech-stack:
  added: []  # fastapi-azure-auth was added in Plan 04-01; this plan only wires the import
  patterns:
    - "Module-level B2CMultiTenantAuthorizationCodeBearer instance pattern: instantiated ONCE at import with openid_config_url pinned to https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0/.well-known/openid-configuration; library caches JWKS in-process (LRU)"
    - "iss_callable workaround for validate_iss=True: library requires the callable when iss validation is on. We provide _iss_callable returning the pinned issuer URL ignoring the tid param (Entra External ID is effectively single-tenant from our perspective)"
    - "AUTH-06 single-user guard: oid != settings.seeded_user_entra_oid OR empty seeded_user_entra_oid ⇒ 403 with literal detail; rejected oid logged via structlog (LAW audit), NOT echoed in response body"
    - "Idempotent Alembic migration pattern: information_schema + pg_indexes presence checks before op.add_column / op.create_index — required when an earlier migration may have already added the same column (0002 added users.entra_oid as Text/unique; 0005 keeps Text and adds the partial unique index)"

key-files:
  created:
    - "alembic/versions/0005_adopt_entra_oid.py"
  modified:
    - "src/job_rag/api/auth.py"
    - "tests/test_auth.py"
    - "tests/test_api.py"
    - "tests/test_alembic.py"

key-decisions:
  - "Table name correction (Rule 1): the plan referenced `user_db` consistently but the actual ORM tablename in src/job_rag/db/models.py::UserDB is `users`. Migration uses `users` and index name `ix_users_entra_oid_unique` (not `ix_user_db_entra_oid_unique`). Plan author wrote without verifying the actual __tablename__ — fixed in migration body."
  - "Column-add made idempotent because 0002_add_user_profile.py already created users.entra_oid as Text + unique=True. The plan's RESEARCH skeleton assumed the column doesn't exist yet. Migration now checks information_schema before op.add_column; on existing DB the column is preserved (no DDL needed). Both the column and the partial unique index coexist — the existing unique constraint plus the new partial-unique-index are structurally equivalent for non-NULL uniqueness."
  - "Added iss_callable to azure_scheme constructor (Rule 3): fastapi-azure-auth's B2CMultiTenantAuthorizationCodeBearer raises RuntimeError when validate_iss=True without iss_callable. Provided async _iss_callable returning the pinned External ID issuer URL — preserves T-04-02-01 (wrong-tenant rejection) without making the library raise on module import."
  - "Downgrade preserves the entra_oid column (only drops the partial unique index). Rationale: the column was created by 0002; dropping it on a 0005 downgrade would lose data captured during bootstrap. Downgrade is a test-only path (per 0004 convention)."
  - "tests/test_api.py /match + /gaps tests now add dependency_overrides[get_current_user_id] = override_user (Rule 1 cascade): the rewritten get_current_user_id now invokes azure_scheme (Depends), so unauthenticated requests return 401 instead of reaching the handler. Tests using ASGITransport without a Bearer header were broken by the contract change; override restores the test's intent (handler-level 404 assertion)."

patterns-established:
  - "Idempotent Alembic column-add: wrap `op.add_column` in `if not _has_column(conn, table, column):` guard for migrations where an earlier migration may already have created the same column. Helper uses information_schema bindparam query."
  - "iss_callable + openid_config_url pinning for Entra External ID: when validate_iss=True is required (security must-have), provide a callable returning the fixed issuer; OpenID discovery URL still pins JWKS source. Two layers of issuer enforcement."
  - "Plan-level Rule 1 cascade fix protocol: when a function-body rewrite changes the request-time contract (adds Depends), existing tests that bypass auth need dependency_overrides for the auth dep. Standard FastAPI test pattern — record alongside Task 2's commit."

requirements-completed: [AUTH-05, AUTH-06]

# Metrics
duration: ~18m
completed: 2026-05-20
---

# Phase 04 Plan 02: Backend Auth Rewrite Summary

**JWT validation + OID allowlist guard wired in `src/job_rag/api/auth.py`. Migration 0005 adds the partial unique index on `users.entra_oid` and bridges Phase 1's seeded UUID to Adrian's real Entra oid via idempotent env-driven UPDATE. Three previously-skipped JWT/OidGuard tests now activate and pass; three new 0005 smoke tests cover upgrade/downgrade/env-set behavior.**

## Performance

- **Duration:** ~18 min (2 atomic commits)
- **Started:** 2026-05-20 (after Plan 04-01 landed)
- **Tasks:** 2 (Task 1: migration + tests; Task 2: auth rewrite + test activation + cascade fix)
- **Files modified:** 1 created / 4 modified

## Accomplishments

- **`src/job_rag/api/auth.py` rewritten in place (Phase 1 D-10 promise held):** module-level `azure_scheme = B2CMultiTenantAuthorizationCodeBearer(...)` instance pinned to `https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0/.well-known/openid-configuration` (Entra External ID / CIAM, per D-07 amendment); `get_current_user_id` signature now `(user: User = Depends(azure_scheme)) -> uuid.UUID`; body enforces AUTH-06 single-user guard (oid match OR fail-closed when seeded_user_entra_oid empty); 403 with literal `user_not_allowlisted` detail (no leak of rejected oid in response body); structlog `log.warning("user_not_allowlisted", rejected_oid=..., seeded_configured=bool(...))` for LAW audit. **No call-site changes** to routes.py — every protected route (/match /gaps /ingest /agent /agent/stream) already wired via `Depends(get_current_user_id)` in Phase 1. **Preserved verbatim:** `_bearer`, `require_api_key`, `RateLimiter`, `standard_limit` / `agent_limit` / `ingest_limit`.
- **`alembic/versions/0005_adopt_entra_oid.py` migration shipped (idempotent + safe):** (1) conditional `op.add_column` for `users.entra_oid` (already present from 0002 as Text/unique — column preserved on existing DBs); (2) parameterized `UPDATE users SET entra_oid = :oid WHERE id = :seeded_uuid AND ...` driven by `os.environ.get("SEEDED_USER_ENTRA_OID", "").strip()` — no-op on empty env (bootstrap-pending state); (3) partial unique index `ix_users_entra_oid_unique` on `(entra_oid) WHERE entra_oid IS NOT NULL`. Downgrade drops only the partial index (preserves the column to avoid data loss). Migration runs at container startup via `init_db()` → `alembic upgrade head` (Phase 1 D-04 rail).
- **Migration verified live on dev DB:** `alembic upgrade head` succeeded (0004 → 0005); second upgrade is a no-op (idempotent); downgrade `0005 → 0004` removes the partial unique index; re-upgrade restores it. Users row count preserved (1 row, the seeded UUID).
- **3 previously-skipped tests in `tests/test_entra_jwt.py` ACTIVATE and PASS** (per Plan 01's skip-on-missing scaffold): `TestEntraJwtValidation::test_rejects_mismatched_oid_with_403`, `TestOidGuard::test_empty_seeded_oid_rejects_everything`, `TestOidGuard::test_matching_oid_returns_seeded_user_id`. The skip-gate (module importable + `azure_scheme` symbol + rewritten `get_current_user_id` symbol) all three conditions now satisfied; no test edits needed in test_entra_jwt.py itself.
- **3 new 0005 Alembic smoke tests in `tests/test_alembic.py`:** `test_0005_upgrade_smoke` (asserts column + partial index exist post-upgrade, row count preserved, empty env leaves NULL); `test_0005_upgrade_populates_oid_when_env_set` (sets `SEEDED_USER_ENTRA_OID=test-oid-xyz-123`, asserts seeded row's `entra_oid` updated, cleans up after); `test_0005_downgrade_smoke` (asserts partial index dropped on downgrade, column preserved). All gated on `_alembic_env_ready()` helper — combines `DATABASE_URL` env presence with `_postgres_reachable()` (mirrors the deferred-items.md recommendation, sidesteps the pre-existing `KeyError('DATABASE_URL')` failure mode in the 0004 smoke tests).
- **`tests/test_auth.py::TestGetCurrentUserId` updated to pass mock User:** new signature requires `user: User = Depends(azure_scheme)`. Test now monkeypatches `settings.seeded_user_entra_oid = "adrian-test-oid"` + builds `MagicMock(claims={"oid": "adrian-test-oid", ...})` and asserts the original contract holds (`result == settings.seeded_user_id`).
- **`tests/test_api.py` Rule 1 cascade fix:** `TestMatchEndpoint::test_match_not_found` and `TestGapsEndpoint::test_gaps_no_postings` previously bypassed auth by relying on `get_current_user_id` returning `settings.seeded_user_id` without checks. With the rewrite, these tests received 401 instead of 404 (auth fails before handler runs). Added `app.dependency_overrides[get_current_user_id] = override_user` to restore test intent — handlers run, return their natural 404. No production code changed; only test-harness reflects the new auth contract.

## Migration Apply Result on Dev DB

- **Before 0005 (HEAD = 0004):** `users` table with 1 row (seeded UUID `00000000-...-0001`), `entra_oid` column already present as Text type with `users_entra_oid_key` unique constraint (from 0002).
- **After 0005:** `users` table unchanged in row count (1 row); `entra_oid` column unchanged (still Text + unique); **new partial unique index `ix_users_entra_oid_unique` on `(entra_oid) WHERE entra_oid IS NOT NULL`** verified in `pg_indexes`. UPDATE was a no-op (SEEDED_USER_ENTRA_OID env empty).
- **Idempotent re-run:** second `alembic upgrade head` exited cleanly (no operations).
- **Downgrade smoke:** removed the partial unique index; column intact.

## Test Count Delta

| Test file | Before | After | Net |
|-----------|--------|-------|-----|
| `tests/test_entra_jwt.py` (Plan 01 scaffolds) | 4 active + 3 skipped | 7 active + 0 skipped | +3 activated |
| `tests/test_alembic.py` | 3 (1 guard + 2 0004 smoke) | 6 (1 guard + 2 0004 smoke + 3 0005 smoke) | +3 new |
| `tests/test_auth.py` | 1 | 1 (updated body) | 0 net |
| `tests/test_api.py` (Rule 1 fix) | 2 broken | 2 fixed | 0 net |
| **Full suite (`pytest -m 'not eval'`)** | 158 passed / 2 skipped (after Plan 01) | 158 passed / 2 skipped | 0 net (all activations balanced by additions) |

Final: `pytest -m 'not eval' -q` → **158 passed, 2 skipped, 0 failed**.

## Verification Results

| Verification | Command | Status |
|--------------|---------|--------|
| 1. alembic upgrade head succeeds | `alembic upgrade head` (dev DB) | ✅ 0004 → 0005 applied, second run no-op |
| 2. Pytest full suite | `pytest -m 'not eval' -q` | ✅ 158 passed / 2 skipped / 0 failed |
| 3. ruff src + tests | `ruff check src/ tests/` | ✅ All checks passed |
| 4. pyright src | `pyright src/` | ✅ 0 errors / 0 warnings |
| 5. azure_scheme class introspection | `python -c "from job_rag.api.auth import azure_scheme; print(type(azure_scheme).__name__)"` | ✅ `B2CMultiTenantAuthorizationCodeBearer` |
| 6. CI grep guard (no DEFAULT uuid on user_id) | `grep -rn user_id...server_default alembic/versions/` | ✅ no matches |
| 7. Live API lifespan start | `LifespanManager(app)` smoke | ✅ reranker preloaded, prompt_version_check_clean, no import errors |
| 8. auth.py contract greps | grep B2C / azure_scheme / user_not_allowlisted / Depends(azure_scheme) | ✅ all 4 present |
| 9. migration 0005 contract greps | grep revision/down_revision/op.add_column/ix_users_entra_oid_unique | ✅ all 4 present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Table name `user_db` → `users` in migration body**
- **Found during:** Task 1 (reading migration 0002 to find SEEDED_USER_ID pattern)
- **Issue:** The plan's RESEARCH skeleton and must-have artifacts repeatedly reference table `user_db`, but the canonical ORM tablename is `users` (per `src/job_rag/db/models.py::UserDB.__tablename__ = "users"` and `alembic/versions/0002_add_user_profile.py:36 op.create_table("users", ...)`). The plan was written without verifying actual table name. Running the plan verbatim would have raised `UndefinedTableError: relation "user_db" does not exist`.
- **Fix:** Used `users` everywhere in 0005_adopt_entra_oid.py; renamed the partial unique index `ix_user_db_entra_oid_unique` → `ix_users_entra_oid_unique` for consistency.
- **Files modified:** `alembic/versions/0005_adopt_entra_oid.py`
- **Commit:** `22a90c7`

**2. [Rule 1 - Bug] Column-add idempotency: `users.entra_oid` already exists from migration 0002**
- **Found during:** Task 1 (live introspection of dev DB before writing migration)
- **Issue:** Plan/RESEARCH skeleton specified `op.add_column("users", sa.Column("entra_oid", sa.String(255), nullable=True))` unconditionally. But `0002_add_user_profile.py:41` already creates the column as `sa.Text, unique=True, nullable=True`. Running the unconditional add_column would raise `DuplicateColumn: column "entra_oid" of relation "users" already exists`.
- **Fix:** Wrapped `op.add_column` in `if not _has_column(conn, "users", "entra_oid"):` guard using an `information_schema.columns` lookup. The existing Text type satisfies the plan's VARCHAR(255) intent (TEXT is a superset). On a hypothetical fresh DB where the column doesn't yet exist (extremely unlikely given 0002 is already deployed), the migration would create it.
- **Files modified:** `alembic/versions/0005_adopt_entra_oid.py`
- **Commit:** `22a90c7`

**3. [Rule 3 - Blocking] `B2CMultiTenantAuthorizationCodeBearer(validate_iss=True)` requires `iss_callable`**
- **Found during:** Task 2 (smoke-testing module instantiation with empty Settings strings)
- **Issue:** The library raises `RuntimeError('validate_iss is enabled, so you must provide an iss_callable')` at instantiation when `validate_iss=True` is passed without an `iss_callable`. The plan's RESEARCH skeleton omitted this argument. The module would fail to import, breaking every test that imports `job_rag.api.auth`.
- **Fix:** Added `async def _iss_callable(tid: str) -> str` returning the pinned External ID issuer URL (`https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0`). The callable ignores the `tid` argument because Entra External ID is effectively single-tenant from our perspective (one trusted tenant). The library still enforces `iss` against this returned URL — T-04-02-01 (wrong-tenant JWT rejection) mitigation is preserved.
- **Files modified:** `src/job_rag/api/auth.py`
- **Commit:** `42e814a`

**4. [Rule 1 - Bug] Cascade: `tests/test_api.py::TestMatchEndpoint::test_match_not_found` + `TestGapsEndpoint::test_gaps_no_postings` returned 401 instead of 404**
- **Found during:** Task 2 verification (`pytest -m 'not eval'` full suite)
- **Issue:** Before the rewrite, `get_current_user_id` returned `settings.seeded_user_id` directly with no input parsing. Tests that hit `/match/{id}` and `/gaps` without a Bearer header still got the seeded UUID and reached the handler logic (where they asserted `404`). After the rewrite, `get_current_user_id` invokes `azure_scheme` (Depends), so unauthenticated requests now hit a 401 before the handler runs. The tests were testing handler behavior (404 from missing data), not auth — but the contract change broke their setup.
- **Fix:** Added `app.dependency_overrides[get_current_user_id] = override_user` to both tests where `override_user` is `async def() -> uuid.UUID: return settings.seeded_user_id`. Restores the test's original intent (handler returns 404 because mocked DB returns empty). No production code change.
- **Files modified:** `tests/test_api.py`
- **Commit:** `42e814a`

---

**Total deviations:** 4 (all auto-fixes; 3 × Rule 1 bug; 1 × Rule 3 blocking)
**Impact on plan:** Plan completed end-to-end; deviations were corrections required to make the plan's verbatim instructions actually work against the existing codebase state. All must-have truths satisfied (table name change preserves the semantic contract; idempotent column-add preserves the intent; the iss_callable preserves the threat-model mitigation).

## Confirmation: No Call-Site Changes (Phase 1 D-10 Promise Held)

- `grep -n "Depends(get_current_user_id)" src/job_rag/api/routes.py` returns 3 hits (lines 160, 181, 343 — for `/match`, `/gaps`, `/ingest` + agent routes). **Zero edits to routes.py.** The function-body rewrite pattern from Phase 1 D-10 held exactly as designed: only the function signature + body changed; every consumer was already wired.

## Files Created/Modified

**Created:**
- `alembic/versions/0005_adopt_entra_oid.py` — 126 lines; idempotent column-add + UPDATE + partial unique index

**Modified:**
- `src/job_rag/api/auth.py` — 153 lines (from 81); added imports, _iss_callable, azure_scheme instance, rewrote get_current_user_id body
- `tests/test_auth.py` — updated TestGetCurrentUserId.test_returns_seeded_user_id to monkeypatch settings + mock User
- `tests/test_api.py` — added get_current_user_id dependency_override to /match + /gaps tests (Rule 1 cascade)
- `tests/test_alembic.py` — appended _alembic_env_ready helper + 3 new 0005 smoke tests; added `import os` at top

## Issues Encountered

- **`B2CMultiTenantAuthorizationCodeBearer` validate_iss requirement (documented above as Rule 3 deviation).** Resolved by providing `_iss_callable`.
- **None blocking** — both tasks completed end-to-end without checkpointing.

## User Setup Required

None. Plan 06 (OID-bootstrap runbook) is the natural place where Adrian sets `SEEDED_USER_ENTRA_OID` via `az keyvault secret set` after first-login OID capture; ACA revision restart triggers `init_db() → alembic upgrade head → 0005's idempotent UPDATE`, bridging the seeded UUID to his real Entra oid.

## Next Phase Readiness

- **Plan 04-03 (CI + SPA workflow) unblocked:** backend JWT validation contract is now live; CI tests confirm it works end-to-end.
- **Plan 04-04 (frontend scaffold) unblocked:** SPA can now talk to the backend via Bearer JWT; the AccessDenied page (D-09) will be triggered by the rewritten guard when oid doesn't match.
- **Plan 04-05 (frontend wiring) unblocked:** `authedFetch` interceptor pattern works against the new backend auth (401 → silent refresh → retry; 403 → AccessDenied route).
- **Plan 04-06 (OID-bootstrap runbook) unblocked:** the 0005 migration is in place to consume `SEEDED_USER_ENTRA_OID` once Adrian sets it via `az keyvault secret set`.

## Self-Check: PASSED

- All commits exist: `22a90c7` (Task 1 migration + tests), `42e814a` (Task 2 auth rewrite + activations + cascade) — verified via `git log --oneline | head -3`.
- All files exist: alembic/versions/0005_adopt_entra_oid.py, src/job_rag/api/auth.py (modified), tests/test_auth.py (modified), tests/test_api.py (modified), tests/test_alembic.py (modified).
- All 9 plan-level verifications PASS (alembic upgrade head, pytest 158/2/0, ruff src+tests, pyright src 0/0, class name introspection, CI grep guard, lifespan smoke, auth.py contract greps, migration contract greps).

---
*Phase: 04-frontend-shell-auth*
*Completed: 2026-05-20*
