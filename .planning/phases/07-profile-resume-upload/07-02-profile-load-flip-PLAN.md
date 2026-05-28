---
phase: 07-profile-resume-upload
plan: 02
type: execute
wave: 1
depends_on: [01]
files_modified:
  - src/job_rag/services/matching.py
  - src/job_rag/api/routes.py
  - src/job_rag/services/analytics.py
  - src/job_rag/mcp_server/tools.py
  - alembic/versions/0006_seed_user_profile.py
  - tests/test_matching.py
  - tests/test_alembic.py
  - tests/test_analytics.py
  - tests/test_mcp_server.py
  - tests/test_api.py
autonomous: true
requirements: [PROF-01]
requirements_addressed: [PROF-01]

must_haves:
  truths:
    - "load_profile() reads from the user_profile DB row, not data/profile.json"
    - "load_profile() is async and accepts an AsyncSession positional argument"
    - "All five existing call sites (/match, /gaps, analytics, two MCP tools) compile and pass tests after the flip"
    - "Alembic 0006_seed_user_profile migration inserts Adrian's seed row idempotently (ON CONFLICT DO NOTHING)"
    - "Re-running `alembic upgrade head` against an already-seeded DB is a no-op"
    - "grep -rn 'profile.json' src/ returns no production read paths (only data/README.md doc reference)"
  artifacts:
    - path: "src/job_rag/services/matching.py"
      provides: "async def load_profile(session, *, user_id=None) DB-backed"
      contains: "async def load_profile"
    - path: "alembic/versions/0006_seed_user_profile.py"
      provides: "Data migration: idempotent UPSERT of Adrian's profile row"
      contains: "ON CONFLICT (user_id) DO NOTHING"
    - path: "tests/test_matching.py"
      provides: "3 new tests: returns_seeded_row, fails_when_row_missing, independent_of_filesystem"
      contains: "test_load_profile_returns_seeded_row"
    - path: "tests/test_alembic.py"
      provides: "Seed migration round-trip test"
      contains: "seed_user_profile"
  key_links:
    - from: "src/job_rag/services/matching.py::load_profile"
      to: "user_profile DB row"
      via: "select(UserProfileDB).where(UserProfileDB.user_id == uid)"
      pattern: "select.*UserProfileDB"
    - from: "alembic/versions/0006_seed_user_profile.py"
      to: "alembic/versions/0005_adopt_entra_oid.py"
      via: "down_revision chain"
      pattern: "down_revision.*0005"
    - from: "src/job_rag/api/routes.py /match /gaps"
      to: "await load_profile(session, user_id=user_id)"
      via: "async call with session arg"
      pattern: "await load_profile"
---

<objective>
Flip the `load_profile()` body from a JSON file read to an async DB query against the `user_profile` table (PROF-01). Ship the 0006 Alembic migration that idempotently seeds Adrian's row from an embedded dict literal (D-03). Update all five existing call sites to `await load_profile(session, user_id=...)` and update mocks in two test files to async mocks. After this plan lands, `data/profile.json` is no longer a runtime read path anywhere in `src/`.

Purpose: Phase 1 D-07 deliberately built the `(*, user_id=None, path=None)` signature as the forward hook for this exact moment. Phase 5 D-06 deferred the flip to Phase 7. The dashboard CV-vs-market widget already calls `load_profile()` server-side — the function body change preserves shape, but the async signature requires updating callers in lockstep.
Output: 1 migration + 1 modified service + 4 modified callers + 4 modified test files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-RESEARCH.md
@.planning/phases/07-profile-resume-upload/07-PATTERNS.md
@.planning/phases/07-profile-resume-upload/07-VALIDATION.md
@src/job_rag/services/matching.py
@src/job_rag/db/models.py
@alembic/versions/0005_adopt_entra_oid.py
@data/profile.json
@src/job_rag/api/routes.py
@src/job_rag/services/analytics.py
@src/job_rag/mcp_server/tools.py
@tests/test_matching.py
@tests/test_analytics.py
@tests/test_mcp_server.py

<interfaces>
<!-- Phase 7 target signature (per RESEARCH §4 lines 184-201) -->
```python
async def load_profile(
    session: AsyncSession, *, user_id: UUID | None = None,
) -> UserSkillProfile:
    """Load user skill profile from the `user_profile` DB row (PROF-01)."""
    uid = user_id or settings.seeded_user_id
    stmt = select(UserProfileDB).where(UserProfileDB.user_id == uid)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"user_profile row missing for user_id={uid}")
    return UserSkillProfile(
        skills=[UserSkill(**s) for s in json.loads(row.skills_json)],
        target_roles=json.loads(row.target_roles_json),
        preferred_locations=json.loads(row.preferred_locations_json),
        min_salary=row.min_salary_eur,
        remote_preference=RemotePolicy(row.remote_preference),
    )
```

<!-- UserProfileDB columns (db/models.py:118-147) -->
- user_id: UUID PK
- skills_json: JSON text
- target_roles_json: JSON text
- preferred_locations_json: JSON text
- min_salary_eur: int | None
- remote_preference: str
- updated_at: timestamptz

<!-- Phase 1 D-08: canonical seeded UUID literal (matches 0005 line 41) -->
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"

<!-- Call sites to flip (from RESEARCH §4 lines 156-165) -->
| File | Line | Context |
| src/job_rag/api/routes.py | 192 | /match/{posting_id} handler |
| src/job_rag/api/routes.py | 216 | /gaps handler |
| src/job_rag/mcp_server/tools.py | 121 | match_skills MCP tool |
| src/job_rag/mcp_server/tools.py | 147 | skill_gaps MCP tool |
| src/job_rag/services/analytics.py | 295 | _compute_cv_vs_market |

<!-- Test mock sites (RESEARCH §4 lines 166-168) -->
| File | Lines | Action |
| tests/test_mcp_server.py | 126, 164 | Replace MagicMock with AsyncMock(return_value=UserSkillProfile(...)) |
| tests/test_analytics.py | 357, 378, 403, 417 | Replace lambda mock with `async def fake_load_profile(session, *, user_id): ...` |
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| API handler → load_profile() → DB | An untrusted JWT-derived user_id reaches the DB query; safe because it's parameter-bound (no SQL injection vector) |
| migration → existing rows | Re-running migrations against a populated DB must not corrupt or duplicate the seed row |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-01 | Tampering / Integrity | load_profile DB read | mitigate | Read uses parameter-bound `select().where()` (SQLAlchemy core); never string-interpolates `user_id`. Pydantic validation on the JSON columns catches corrupt rows → `ValidationError` → 500 (data-integrity bug, not user error). Validated by `test_load_profile_returns_seeded_row` (07-02-01) and `test_load_profile_fails_when_row_missing` (07-02-02). |
| T-07-03 | Data migration / Repeatable upgrade | alembic 0006 seed migration | mitigate | `ON CONFLICT (user_id) DO NOTHING` is idempotent against PG16 prod + PG17 dev; second `alembic upgrade head` is a no-op. Downgrade deletes ONLY the seeded UUID row. Validated by `tests/test_alembic.py::test_seed_user_profile_idempotent` (07-02-06). |
</threat_model>

<tasks>

<task type="auto" id="07-02-01" tdd="true">
  <name>Task 1: Write 0006 seed migration + load_profile body-flip + tests (RED→GREEN)</name>
  <files>alembic/versions/0006_seed_user_profile.py, src/job_rag/services/matching.py, tests/test_matching.py, tests/test_alembic.py</files>
  <read_first>
    - src/job_rag/services/matching.py (existing body lines 14-35 — the signature pre-built by Phase 1 D-07)
    - src/job_rag/db/models.py (lines 118-147 — UserProfileDB column shape)
    - alembic/versions/0005_adopt_entra_oid.py (FULL file — revision header pattern lines 31-48; SEEDED_USER_UUID literal at line 41; idempotency pattern lines 51-71)
    - data/profile.json (the actual seed contents — to be embedded as dict literal)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §4 lines 154-205 (new load_profile body)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §5 lines 207-270 (seed migration shape)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §5 lines 237-294 (migration revision chain)
    - tests/test_matching.py (existing — APPEND tests; do not overwrite)
  </read_first>
  <behavior>
    - Test 1 (test_load_profile_returns_seeded_row): given a session with the seeded row, `await load_profile(session, user_id=SEEDED_USER_UUID)` returns a `UserSkillProfile` whose `skills`, `target_roles`, `preferred_locations`, `min_salary`, `remote_preference` exactly match `data/profile.json` contents
    - Test 2 (test_load_profile_fails_when_row_missing): given a session with NO row for a given UUID, `await load_profile(session, user_id=<random_uuid>)` raises `RuntimeError` with message "user_profile row missing for user_id={uuid}"
    - Test 3 (test_load_profile_independent_of_filesystem): monkeypatch `settings.profile_path` to a nonexistent path; `await load_profile(session)` still succeeds (proves no file read)
    - Test 4 (test_seed_user_profile_idempotent): run `alembic upgrade head` twice; second run is a no-op (row count unchanged, no error)
    - Test 5 (test_seed_user_profile_downgrade): `alembic downgrade -1` deletes ONLY the seeded UUID row; other rows (if any) untouched
  </behavior>
  <action>
**Step A — Create the 0006 migration (per RESEARCH §5 + PATTERNS §5):**

Create `alembic/versions/0006_seed_user_profile.py`. Generate the `_PROFILE` dict literal by reading `data/profile.json` AT MIGRATION-AUTHOR TIME (i.e., now, during this task) and pasting its contents as a Python literal. Do NOT use `Path(...).read_text()` at runtime — `data/` is gitignored at the container layer per RESEARCH §5 lines 268-270; runtime read would crash on fresh ACA boot.

Workflow:
1. Read `data/profile.json` via the Read tool — get the actual JSON contents.
2. Convert to a Python literal (you can paste the JSON; Python accepts a dict literal that matches JSON shape with minor adjustments — `true`→`True`, `null`→`None`).
3. Embed in the migration as `_PROFILE = {...}`.

Migration shape:
```python
"""seed Adrian's user_profile row (PROF-01 / Phase 7 D-03)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-27
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase 1 D-08: canonical seeded UUID. Migrations do not import from
# job_rag.config; this literal MUST match settings.seeded_user_id.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"

# Embedded snapshot of data/profile.json (D-03/D-04 — data/ is gitignored
# at the container layer; runtime file-read would crash on fresh ACA boot).
_PROFILE = {
    "skills": [...],                # paste from data/profile.json
    "target_roles": [...],
    "preferred_locations": [...],
    "min_salary": ...,              # int or None
    "remote_preference": "remote",  # or whatever data/profile.json has
}


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO user_profile "
            "(user_id, skills_json, target_roles_json, preferred_locations_json, "
            " min_salary_eur, remote_preference, updated_at) "
            "VALUES (:uid, :skills, :roles, :locs, :sal, :remote, now()) "
            "ON CONFLICT (user_id) DO NOTHING"
        ).bindparams(
            uid=SEEDED_USER_UUID,
            skills=json.dumps(_PROFILE["skills"]),
            roles=json.dumps(_PROFILE["target_roles"]),
            locs=json.dumps(_PROFILE["preferred_locations"]),
            sal=_PROFILE["min_salary"],
            remote=_PROFILE["remote_preference"],
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM user_profile WHERE user_id = :uid"
        ).bindparams(uid=SEEDED_USER_UUID)
    )
```

Verify chain: `uv run alembic history | head -10` should show `0005 -> 0006 (head)`.

**Step B — Flip load_profile body (per RESEARCH §4 lines 172-201):**

Edit `src/job_rag/services/matching.py`. Replace the CURRENT `load_profile` function (lines 14-35) with the async DB-query version:

```python
async def load_profile(
    session: AsyncSession, *, user_id: UUID | None = None,
) -> UserSkillProfile:
    """Load user skill profile from the `user_profile` DB row (PROF-01).

    Replaces the Phase 1 JSON file read (D-07 forward hook) with an async DB
    query (Phase 7 D-01/D-02). All callers MUST be updated to `await
    load_profile(session, ...)`.
    """
    uid = user_id or settings.seeded_user_id
    stmt = select(UserProfileDB).where(UserProfileDB.user_id == uid)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        # Seed migration D-03 guarantees the row; missing = data-integrity bug.
        raise RuntimeError(f"user_profile row missing for user_id={uid}")
    return UserSkillProfile(
        skills=[UserSkill(**s) for s in json.loads(row.skills_json)],
        target_roles=json.loads(row.target_roles_json),
        preferred_locations=json.loads(row.preferred_locations_json),
        min_salary=row.min_salary_eur,
        remote_preference=RemotePolicy(row.remote_preference),
    )
```

Imports at module top to ADD:
- `from uuid import UUID`
- `from sqlalchemy import select`
- `from sqlalchemy.ext.asyncio import AsyncSession`
- `from job_rag.db.models import UserProfileDB`
- (if not present) `import json`

Imports to REMOVE:
- `from pathlib import Path` (now unused — verify nothing else in matching.py uses Path)
- The `path` kwarg from the signature

Keep `_normalize_skill`, `_ALIAS_GROUPS`, `_ALIAS_INDEX`, `_skill_matches` untouched (Plan 04 imports `_normalize_skill` for `compute_skills_diff`).

**Step C — Write the three load_profile tests (APPEND to `tests/test_matching.py`):**

```python
# Phase 7 D-01/D-02 — load_profile DB-backed tests (PROF-01)
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_rag.config import settings
from job_rag.db.models import UserProfileDB
from job_rag.services.matching import load_profile


SEEDED_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_load_profile_returns_seeded_row(db_session: AsyncSession):
    """PROF-01 / D-01: load_profile reads from user_profile, not data/profile.json."""
    # Assumes the seed migration ran via the test-session fixture (alembic upgrade head).
    profile = await load_profile(db_session, user_id=SEEDED_UUID)
    assert len(profile.skills) > 0
    # Compare to data/profile.json contents
    raw = json.loads(Path("data/profile.json").read_text())
    assert {s.name for s in profile.skills} == {s["name"] for s in raw["skills"]}


@pytest.mark.asyncio
async def test_load_profile_fails_when_row_missing(db_session: AsyncSession):
    """D-02: defensive — raises RuntimeError if seed row missing."""
    bogus = uuid.uuid4()  # guaranteed not seeded
    with pytest.raises(RuntimeError, match="user_profile row missing"):
        await load_profile(db_session, user_id=bogus)


@pytest.mark.asyncio
async def test_load_profile_independent_of_filesystem(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """D-05 criterion 2: load_profile does NOT read data/profile.json at runtime."""
    monkeypatch.setattr(settings, "profile_path", "/nonexistent/path/profile.json")
    profile = await load_profile(db_session, user_id=SEEDED_UUID)
    assert len(profile.skills) > 0
```

The `db_session` fixture must yield an `AsyncSession` against a test DB where Alembic head has been applied. If `tests/conftest.py` does not provide it, consult the existing fixture pattern (matching what test_api.py uses) and add a session-scoped fixture that runs `alembic upgrade head` before tests + yields an AsyncSession. If conftest already has `db_session` or equivalent, REUSE the existing name.

**Step D — Write the seed migration tests (`tests/test_alembic.py`, append or new):**

```python
"""Tests for alembic migrations (Phase 7 0006_seed_user_profile)."""
import subprocess
import uuid

import pytest
from sqlalchemy import text

SEEDED_UUID = "00000000-0000-0000-0000-000000000001"


def test_seed_user_profile_migration_inserts_row(alembic_session):
    """0006 upgrade inserts Adrian's seed row."""
    result = alembic_session.execute(
        text("SELECT COUNT(*) FROM user_profile WHERE user_id = :u").bindparams(u=SEEDED_UUID)
    ).scalar()
    assert result == 1


def test_seed_user_profile_idempotent(alembic_session):
    """D-03 + T-07-03: re-running upgrade is a no-op (ON CONFLICT DO NOTHING)."""
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)
    result = alembic_session.execute(
        text("SELECT COUNT(*) FROM user_profile WHERE user_id = :u").bindparams(u=SEEDED_UUID)
    ).scalar()
    assert result == 1  # still exactly one row
```

`alembic_session` fixture provides a sync `Session` against the test DB with migrations applied. If `tests/conftest.py` lacks it, add via the same pattern existing migration tests use (or use SQLAlchemy `engine.connect()` + sync session). If a session-fixture pattern already exists in `tests/test_alembic.py` (file may be new from Plan 01), align to that.

**Step E — Verify RED → GREEN cycle:**

1. Run the 3 matching.py tests FIRST (RED — before flipping the body): `uv run pytest tests/test_matching.py -k load_profile -x`. Expected: red (tests reference `db_session` and DB query that doesn't exist yet, OR tests fail because old body still reads JSON).
2. Apply Step A + B (migration + body-flip).
3. Run: `uv run alembic upgrade head` to apply the migration to the local dev DB.
4. Re-run tests — expected GREEN.
5. Run the alembic tests: `uv run pytest tests/test_alembic.py -k seed_user_profile -x`. Expected GREEN.
  </action>
  <verify>
    <automated>uv run alembic history | grep '0006 -> head\|0005 -> 0006' && uv run alembic upgrade head 2>&1 | tail -5 && uv run pytest tests/test_matching.py -k load_profile -x && uv run pytest tests/test_alembic.py -k seed_user_profile -x</automated>
  </verify>
  <acceptance_criteria>
    - `alembic/versions/0006_seed_user_profile.py` exists with `revision = "0006"` and `down_revision = "0005"`
    - `uv run alembic upgrade head` exits 0; second run is a no-op (no errors, no duplicate-key violations)
    - `uv run pytest tests/test_matching.py -k load_profile_returns_seeded_row -x` passes (VALIDATION 07-02-01)
    - `uv run pytest tests/test_matching.py -k load_profile_fails_when_row_missing -x` passes (VALIDATION 07-02-02)
    - `uv run pytest tests/test_matching.py -k load_profile_independent_of_filesystem -x` passes (VALIDATION 07-02-03)
    - `uv run pytest tests/test_alembic.py -k seed_user_profile -x` passes (VALIDATION 07-02-06)
    - `src/job_rag/services/matching.py` signature line matches `async def load_profile(session: AsyncSession, *, user_id: UUID | None = None) -> UserSkillProfile`
    - No `Path(...).read_text()` or `profile_path` reference remains in the new `load_profile` body
  </acceptance_criteria>
  <done>
    - Migration applied locally; both new tests files green
    - `uv run pyright src/job_rag/services/matching.py` passes
  </done>
</task>

<task type="auto" id="07-02-02">
  <name>Task 2: Flip 5 call sites + update 2 test mock files + verify integration suite</name>
  <files>src/job_rag/api/routes.py, src/job_rag/services/analytics.py, src/job_rag/mcp_server/tools.py, tests/test_mcp_server.py, tests/test_analytics.py, tests/test_api.py</files>
  <read_first>
    - src/job_rag/api/routes.py (lines 171-200 — `/match` handler; lines 195-225 — `/gaps` handler; existing `session: Session` Depends pattern at line 175)
    - src/job_rag/services/analytics.py (line 295 area — `_compute_cv_vs_market` calling `load_profile`)
    - src/job_rag/mcp_server/tools.py (lines 100-160 — `match_skills` and `skill_gaps` MCP tools; the `async with AsyncSessionLocal() as session:` block already exists per RESEARCH §4 line 162)
    - tests/test_mcp_server.py (lines 120-170 area — existing `patch("job_rag.mcp_server.tools.load_profile")` calls)
    - tests/test_analytics.py (lines 350-420 area — existing `monkeypatch.setattr(analytics, "load_profile", ...)` calls)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §4 lines 156-168 (call site table)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §6 lines 296-339 (call-site flip pattern)
  </read_first>
  <action>
**Step A — Flip call sites (5 locations):**

1. `src/job_rag/api/routes.py` `/match/{posting_id}` handler (around line 192):
   - BEFORE: `profile = load_profile(user_id=user_id)`
   - AFTER: `profile = await load_profile(session, user_id=user_id)`
   - The handler already has `session: Session` (which is `Annotated[AsyncSession, Depends(get_session)]`) and is already `async def`. No signature change needed.

2. `src/job_rag/api/routes.py` `/gaps` handler (around line 216):
   - Same flip: `profile = await load_profile(session, user_id=user_id)`.

3. `src/job_rag/services/analytics.py` `_compute_cv_vs_market` (around line 295):
   - Function already takes `session: AsyncSession`. Flip the call:
   - BEFORE: `profile = load_profile(user_id=user_id)`
   - AFTER: `profile = await load_profile(session, user_id=user_id)`
   - Ensure the enclosing function is `async def` (it should be — Phase 5 D-06 already async).

4. `src/job_rag/mcp_server/tools.py` `match_skills` (around line 121):
   - The function opens `async with AsyncSessionLocal() as session:` per RESEARCH §4 line 162. REUSE that session:
   - BEFORE: `profile = load_profile(user_id=settings.seeded_user_id)` (or similar)
   - AFTER: `profile = await load_profile(session, user_id=settings.seeded_user_id)`

5. `src/job_rag/mcp_server/tools.py` `skill_gaps` (around line 147):
   - Same as #4.

After all flips, run `grep -rn "load_profile" src/` and confirm:
- All callers use `await load_profile(session, ...)` form
- No caller passes `path=...` (now-removed kwarg)

**Step B — Update test mocks (2 files):**

1. `tests/test_mcp_server.py` lines 126 + 164 area: replace sync mock with async mock per RESEARCH §4 lines 167-168:
   ```python
   # Before
   patch("job_rag.mcp_server.tools.load_profile")
   # After
   from unittest.mock import AsyncMock
   patch(
       "job_rag.mcp_server.tools.load_profile",
       AsyncMock(return_value=UserSkillProfile(skills=[...], ...)),
   )
   ```
   If the existing test relies on `MagicMock` return_value semantics, switch to `AsyncMock`. The mock function signature must accept `(session, *, user_id=None)` since callers now pass session as the first positional arg.

2. `tests/test_analytics.py` lines 357, 378, 403, 417: replace lambda mocks with async functions:
   ```python
   # Before
   monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: UserSkillProfile(...))
   # After
   async def fake_load_profile(session, *, user_id):
       return UserSkillProfile(skills=[...], ...)
   monkeypatch.setattr(analytics, "load_profile", fake_load_profile)
   ```

**Step C — Verify the integration test suite:**

Run:
```bash
uv run pytest tests/test_api.py -k "match or gaps" -x
uv run pytest tests/test_analytics.py -k "cv_vs_market" -x
uv run pytest tests/test_mcp_server.py -k "match_skills or skill_gaps" -x
```

All three command groups must pass. Per VALIDATION 07-02-05: "/match/{posting_id}, /gaps, /dashboard/cv-vs-market continue to return identical shapes after the flip."

**Step D — Grep proof (VALIDATION 07-02-04):**

Run `grep -rn "profile.json" src/` and confirm the ONLY match is in `data/README.md` (which is not under `src/`). The grep against `src/` should return zero matches.

Also run `grep -rn "load_profile" src/` and confirm every match uses the `await load_profile(session, ...)` form (no bare `load_profile(...)` calls remain).
  </action>
  <verify>
    <automated>! grep -rn 'profile.json' src/ && uv run pytest tests/test_api.py tests/test_analytics.py tests/test_mcp_server.py -k 'match or gaps or skill_gaps or cv_vs_market' -x && uv run pyright src/</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "profile.json" src/` returns 0 matches (VALIDATION 07-02-04)
    - `grep -rn "load_profile" src/` shows all callers use `await load_profile(session, ...)` form
    - `uv run pytest tests/test_api.py tests/test_analytics.py tests/test_mcp_server.py -k "match or gaps or skill_gaps or cv_vs_market"` exits 0 (VALIDATION 07-02-05)
    - `uv run pyright src/` exits 0 (no type errors from signature change)
    - Full backend suite still passes: `uv run pytest tests/ -x` exits 0 (no test breaks introduced by the flip)
  </acceptance_criteria>
  <done>
    - 5 call sites updated + 2 mock-test files updated
    - Full backend suite green (`uv run pytest tests/ -x`)
    - PROF-01 complete; no `data/profile.json` runtime read path anywhere in `src/`
  </done>
</task>

</tasks>

<verification>
After both tasks land:

```bash
# Static — no profile.json reads remain
! grep -rn "profile.json" src/ 2>&1

# Static — signature shape
grep -E "async def load_profile" src/job_rag/services/matching.py

# Migration applied + idempotent
uv run alembic upgrade head
uv run alembic upgrade head  # second run no-op

# Targeted tests
uv run pytest tests/test_matching.py -k load_profile -x
uv run pytest tests/test_alembic.py -k seed_user_profile -x

# Integration — all 5 call sites still work
uv run pytest tests/test_api.py tests/test_analytics.py tests/test_mcp_server.py -k "match or gaps or skill_gaps or cv_vs_market" -x

# Type safety
uv run pyright src/

# Full suite
uv run pytest tests/ -x
```

All commands must exit 0.
</verification>

<success_criteria>
- PROF-01 closed: load_profile reads from user_profile DB row, not data/profile.json
- Phase 5 dashboard's CV-vs-market widget still works (transparent body change)
- Migration is idempotent (T-07-03 mitigated)
- All 7 acceptance criteria across both tasks green
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-02-SUMMARY.md` capturing:
- Migration 0006 file size + commit SHA
- Pre/post line counts in matching.py (proof of body change)
- List of 5 callers + 2 mock files updated with brief notes on any non-obvious changes
- Confirmation that `data/profile.json` remains in repo as reference snapshot (not deleted)
</output>
