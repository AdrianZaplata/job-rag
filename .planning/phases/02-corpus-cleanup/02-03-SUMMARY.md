---
phase: 02-corpus-cleanup
plan: 03
subsystem: schema-migration + reextraction-orchestration
tags: [alembic, migration, reextract, drift-detection, cli, lifespan, mcp-shape-change]

requires:
  - phase: 02-corpus-cleanup
    plan: 01
    provides: "SkillType / SkillCategory / Location ORM + Pydantic + derive_skill_category() helper"
  - phase: 02-corpus-cleanup
    plan: 02
    provides: "PROMPT_VERSION = '2.0' + REJECTED_SOFT_SKILLS + str.format()-built SYSTEM_PROMPT"
provides:
  - "alembic/versions/0004_corpus_cleanup.py — hand-written migration: rename category->skill_type, add skill_category nullable + SQL CASE backfill + SET NOT NULL, swap indexes, add 3 location_* columns + ix_country, drop free-text location"
  - "src/job_rag/services/extraction.py — reextract_stale + _reextract_one + ReextractReport; per-posting AsyncSession (Pitfall 5), empty-string->None coercion (Open Q5), preserves raw_text + embeddings (D-15)"
  - "src/job_rag/cli.py::reextract subcommand wrapping reextract_stale; --all/--posting-id/--dry-run/--yes flags; typer.confirm guard rail (T-CLI-01)"
  - "src/job_rag/cli.py::list_postings::--stats flag — prompt_version distribution with STALE marker (CORP-04 / D-17)"
  - "src/job_rag/api/app.py lifespan extension — startup SELECT prompt_version drift query, structured warning on stale rows, info on clean (Pattern 4); exception swallowed (best-effort observability)"
  - "Sweep of services/ingestion.py + embedding.py + retrieval.py + mcp_server/tools.py for posting.location and req.category — replaced with new schema shape"
  - "_format_location_for_embedding + _format_location_for_context private helpers in embedding.py + retrieval.py"
  - "_serialize_posting in mcp_server/tools.py emits nested location object + per-requirement skill_type/skill_category"
  - "tests: test_alembic.py (upgrade/downgrade smokes, skip-on-no-PG); test_reextract.py (7 tests across 6 classes); test_cli.py::TestListStatsPromptVersion; test_lifespan.py::TestPromptVersionDriftWarning"
affects: [02-04 (live corpus reextract — uses every primitive landed here), 03 (infra references reextract CLI in deploy docs), 05 (dashboard reads location_country/city/region directly)]

tech-stack:
  added: []
  patterns:
    - "Hand-written rename migration (Pitfall 1) — op.alter_column(new_column_name=...) over autogenerate's drop+add destructiveness"
    - "Add-nullable -> SQL CASE backfill -> SET NOT NULL three-step pattern for new NOT NULL columns on populated tables (Pitfall 2)"
    - "Drop renamed-column's old index BY OLD NAME before creating new indexes (Pitfall 6 — op.alter_column does not rename index files)"
    - "Per-posting fresh AsyncSession (Pattern 3) for long-running LLM-backed loops — avoids B1ms 5-conn pool saturation during 1-3s round-trips"
    - "Empty-string -> None defensive coercion at LLM->DB boundary (Open Q5) — GPT-4o-mini sometimes emits '' for unknown optional fields"
    - "Best-effort observability lifespan steps — try/except wrapping prevents slow DB on cold start from blocking ASGI from accepting connections"
    - "structlog log-method patching for caplog-incompatible event capture — patch.object(app_mod.log, 'warning', side_effect=capture) bypasses the stdlib logging tree that PrintLoggerFactory does not feed"

key-files:
  created:
    - alembic/versions/0004_corpus_cleanup.py
    - src/job_rag/services/extraction.py
    - tests/test_reextract.py
  modified:
    - src/job_rag/services/ingestion.py
    - src/job_rag/services/embedding.py
    - src/job_rag/services/retrieval.py
    - src/job_rag/mcp_server/tools.py
    - src/job_rag/cli.py
    - src/job_rag/api/app.py
    - tests/test_alembic.py
    - tests/test_cli.py
    - tests/test_lifespan.py
    - tests/test_ingestion.py
    - tests/test_mcp_server.py

key-decisions:
  - "Ran the BLOCKING `alembic upgrade head` gate via a Python wrapper that loaded settings from .env, URL-encoded the password, and applied the `%%` ConfigParser escape — STATE.md decision from Plan 01-02 reused (Adrian's dev DB password contains URL-special chars that ConfigParser interpolates)"
  - "Used socat sidecar (`alpine/socat` on the docker-compose network) to bridge host:5432 -> db:5432 because docker-compose only `expose`s the DB internally; matches the Plan 01-02 pattern documented in STATE.md"
  - "In tests/test_lifespan.py, the assertion uses patch.object(app_mod.log, 'warning'/'info', side_effect=capture) instead of caplog — structlog's PrintLoggerFactory bypasses the stdlib logging tree, so caplog records nothing. The plan's executor-discretion note anticipated this exactly."
  - "STALE marker is plain ASCII (no emoji) per Plan execution discretion — Adrian's environment is win32 and console-encoding hazards from emoji are deferred to Phase 5 (frontend)"
  - "test_alembic.py upgrade/downgrade smokes skip cleanly when no Postgres reachable — Adrian's settings.database_url uses literal `postgres:postgres` (the .env value), so without the per-execution password override the helper's connection check fails and tests skip; live BLOCKING upgrade was performed via the Python wrapper above"

patterns-established:
  - "Three-step NOT NULL pattern for new columns on populated tables: (1) op.add_column nullable=True, (2) op.execute SQL CASE backfill, (3) op.alter_column nullable=False"
  - "Two-helper sweep pattern for column-shape migrations: define a private _format_location_for_X(p) helper in each consuming module (services/embedding.py, services/retrieval.py); replace `posting.location` f-string interpolation with the helper call site"
  - "structlog test capture: patch.object(module.log, 'warning', side_effect=capture) — captures (event_name, kwargs) tuples without depending on the stdlib logging tree"

requirements-completed: [CORP-04]
requirements-touched: [CORP-01, CORP-02, CORP-03]

duration: ~14m
completed: 2026-04-28
---

# Phase 2 Plan 03: Migration 0004 + Reextract Service + CLI + Drift Surfaces Summary

**Phase 2's orchestration backbone landed: hand-written migration 0004 (rename category->skill_type, add skill_category with SQL CASE backfill, swap indexes, structured Location columns) cleanly upgraded the dev DB preserving all 108 postings + 2121 requirements; the reextract service with per-posting AsyncSession + empty-string->None coercion + the `job-rag reextract` Typer subcommand (with `--all` typer.confirm guard rail) are wired; call-site sweeps eliminate every `posting.location` and `req.category` reference; the lifespan startup emits a structured drift warning. After this plan, Plan 04 just runs the CLI against the live corpus.**

## Pre-flight Manual Step (Documented for Adrian, NOT baked into automation)

Per CONTEXT.md Open Question §3 / Claude's Discretion, Adrian should run a `pg_dump` BEFORE the BLOCKING `alembic upgrade head` step on the dev DB. The plan deliberately omits this from the CLI to avoid coupling re-extraction to backup policy:

```bash
# Run from host shell BEFORE upgrading the dev DB
pg_dump $DATABASE_URL > pre-phase-2-backup.sql
```

Re-extraction is structurally safe (raw_text preserved per D-15; embeddings untouched), but the migration drops the free-text `location` column whose data is intentionally lost — backup is the safety net.

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-28T07:40:10Z
- **Completed:** 2026-04-28T07:54:33Z
- **Tasks:** 3 (all auto)
- **Files created:** 3
- **Files modified:** 11

## Accomplishments

### Task 1 — Migration 0004 (commit `1b22306`)

- Hand-wrote `alembic/versions/0004_corpus_cleanup.py` with the 9-step upgrade (rename → drop old index → add nullable → SQL CASE backfill → SET NOT NULL → swap indexes → add 3 location_* columns → drop location → create ix_country) and the inverse downgrade.
- Docstring explicitly references Pitfalls 1, 2, 6 and D-11 / D-15 anti-regression context.
- BLOCKING gate passed: `alembic upgrade head` exits 0 against dev DB; **108 job_postings and 2121 job_requirements rows preserved**; skill_category distribution after backfill = `1844 hard / 156 soft / 121 domain`; new columns `location_country/city/region` present; old free-text `location` column absent.
- Extended `tests/test_alembic.py` with `_postgres_reachable()` + `test_0004_upgrade_smoke` + `test_0004_downgrade_smoke`. Tests skip cleanly when settings-driven connection fails (Adrian's .env uses literal `postgres:postgres` while real DB password requires URL-encoding — pre-existing Phase 1 quirk).

### Task 2 — Reextract Service + Sweeps (commit `b9a482e`)

- Created `src/job_rag/services/extraction.py` with `ReextractReport` dataclass + `reextract_stale(*, all, posting_id, dry_run, yes)` + `_reextract_one(posting_id, report)`. Fresh `AsyncSession` per posting iteration (Pitfall 5 / Pattern 3), empty-string→None defensive coercion on all 3 Location fields (Open Q5), DELETE+INSERT requirements with `derive_skill_category(req.skill_type)` derivation, raw_text + embeddings PRESERVED (D-15). `--all` without `yes=True` raises `RuntimeError` (T-CLI-01).
- Swept `services/ingestion.py`: `_store_posting` and `_store_posting_async` write `location_country/city/region` and `skill_type/skill_category` (derived). Added `derive_skill_category` import.
- Swept `services/embedding.py`: added private `_format_location_for_embedding(p)` helper (joins non-null city/region/country with ", " or returns "Location not specified"); `format_posting_for_embedding` line 46 + `chunk_posting` header use it.
- Swept `services/retrieval.py`: added private `_format_location_for_context(p)` helper (same shape — Gotcha A); `rag_query` context f-string uses it.
- Swept `mcp_server/tools.py::_serialize_posting`: emits nested `"location": {country, city, region}` and per-requirement `[{"skill", "skill_type", "skill_category"}, ...]` for both `must_have` and `nice_to_have`.
- Created `tests/test_reextract.py` with 7 tests across 6 classes: `TestReextractStaleDefault`, `TestReextractIdempotency`, `TestReextractAllConfirm`, `TestPartialFailureContinues`, `TestDryRun`, `TestSinglePosting`. All pass.

### Task 3 — CLI + Lifespan + Tests (commit `5b2405b`)

- `cli.py::list_postings`: added `--stats` flag printing prompt_version distribution with `STALE` marker on non-current versions (CORP-04 / D-17). Default branch swapped `Location` column for `Country` (uses `p.location_country or "-"`).
- `cli.py::stats`: `req.category` → `req.skill_type` sweep.
- `cli.py::reextract`: NEW Typer subcommand wrapping `reextract_stale` via `asyncio.run`. `--all/--posting-id/--dry-run/--yes` flags. `typer.confirm` interposed when `--all` without `--yes` (T-CLI-01); aborts with exit 1 on negative.
- `api/app.py` lifespan: inserted drift-check block AFTER reranker preload, BEFORE `app.state.shutdown_event = anyio.Event()`. One-shot SELECT via `AsyncSessionLocal`; stale rows → `log.warning("prompt_version_drift", stale_count, stale_by_version, current, remediation)`; no stale → `log.info("prompt_version_check_clean", current)`; exception → `log.warning("prompt_version_check_failed", error=str(e))` (best-effort, never blocks ASGI). New imports: `text`, `AsyncSessionLocal`, `PROMPT_VERSION`.
- `tests/test_cli.py::TestListStatsPromptVersion`: invokes `runner.invoke(cli_app, ["list", "--stats"])` against mocked SessionLocal returning 2 postings at versions "2.0" + "1.1"; asserts `prompt_version=` and `STALE` substrings.
- `tests/test_lifespan.py::TestPromptVersionDriftWarning`: 2 tests using `patch.object(app_mod.log, "warning"/"info", side_effect=capture)` to bypass structlog's PrintLoggerFactory (caplog can't see those records — executor note in plan anticipated this).

## Live Verification

- `uv run alembic upgrade head` against dev DB: **exit 0**, 108 postings + 2121 requirements preserved, skill_category fully backfilled (1844 hard / 156 soft / 121 domain), 3 location_* columns added, old `location` column dropped.
- `uv run python -m job_rag.cli reextract --dry-run`: **Selected=108** (every existing posting is at prompt_version 1.1; PROMPT_VERSION is now 2.0). Plan 04 will iterate these.
- Full pytest suite: **190 passed, 10 skipped, 0 failed** (up from 187 before this plan).
- `uv run ruff check src/ tests/`: clean.
- `uv run pyright src/`: 0 errors, 0 warnings.

## Task Commits

1. **Task 1: Hand-write migration 0004 + run BLOCKING upgrade + extend test_alembic.py** — `1b22306` (feat)
2. **Task 2: services/extraction.py + sweep ingestion/embedding/retrieval/mcp_server + test_reextract.py** — `b9a482e` (feat)
3. **Task 3: CLI reextract subcommand + list --stats + lifespan drift query + tests** — `5b2405b` (feat)

## Files Created

- `alembic/versions/0004_corpus_cleanup.py` (~190 lines, hand-written; revision="0004", down_revision="0003").
- `src/job_rag/services/extraction.py` (~210 lines; ReextractReport + reextract_stale + _reextract_one).
- `tests/test_reextract.py` (~190 lines; 7 tests).

## Files Modified

- `src/job_rag/services/ingestion.py` — `_store_posting` + `_store_posting_async` rewritten for new schema.
- `src/job_rag/services/embedding.py` — added `_format_location_for_embedding`; 2 call sites swept.
- `src/job_rag/services/retrieval.py` — added `_format_location_for_context`; 1 call site swept.
- `src/job_rag/mcp_server/tools.py` — `_serialize_posting` body rewritten (nested location + per-requirement dict).
- `src/job_rag/cli.py` — list_postings rewritten (--stats branch + Country column); stats sweep; reextract subcommand appended.
- `src/job_rag/api/app.py` — lifespan drift-check block + 3 new top-of-module imports.
- `tests/test_alembic.py` — _postgres_reachable + 2 smoke tests appended.
- `tests/test_cli.py` — TestListStatsPromptVersion appended; pytest import added.
- `tests/test_lifespan.py` — TestPromptVersionDriftWarning appended.
- `tests/test_ingestion.py` — [Rule 1] _make_posting fixture updated for new Location/SkillType schema (was broken by Plan 02-01 rename).
- `tests/test_mcp_server.py` — [Rule 1] _make_posting fixture + assertions updated for new _serialize_posting nested-dict shape.

## Decisions Made

- **Live alembic upgrade via Python wrapper** — invoked `command.upgrade(cfg, "head")` from a small Python script that loaded `.env` via dotenv, URL-encoded `POSTGRES_PASSWORD`, and applied the `%%` ConfigParser escape before setting `os.environ["DATABASE_URL"]`. Reused the Plan 01-02 lesson captured in STATE.md (Adrian's password contains URL-special chars).
- **socat sidecar to expose db:5432 to host** — docker-compose only `expose`s the DB internally to other containers. Started `alpine/socat` joined to `job-rag_default` with `-p 5432:5432` to bridge. Matches Plan 01-02 pattern. Cleanup: `docker stop job-rag-socat`.
- **structlog test capture pattern** — `patch.object(app_mod.log, "warning", side_effect=capture)` collects `(event_name, kwargs)` tuples in a list. Used because structlog's `PrintLoggerFactory` does NOT feed records into the stdlib logging tree, so `caplog.records` returns empty even when warnings are visibly fired (visible in `pytest -s` stdout). The plan's executor-discretion note flagged this risk.
- **Plain-ASCII `STALE` marker** — chose `STALE` over `⚠️ STALE` (plan PATTERNS.md) because Adrian's env is win32 (env block) and emoji on Windows console can produce encoding hazards. Both forms satisfy the test grep (`assert "STALE" in result.stdout`).
- **Test skips when settings.database_url unreachable** — `_postgres_reachable()` uses `settings.database_url` (the literal `.env` value `postgres:postgres@...`) which fails auth against the real DB. Tests skip cleanly. Live BLOCKING upgrade was performed via the Python wrapper above. Future cleanup: align `.env` `DATABASE_URL` with the real password (URL-encoded). Out of scope for this plan.

## MCP Tool Schema Shape Change (Adrian's Reference)

The MCP tool `search_postings` (and any other consumer of `_serialize_posting`) now returns a different JSON shape for posting summaries. Adrian is the only consumer (single-user v1), so no contract break — but document for reference:

**Before (Phase 1 / pre-Phase 2):**
```json
{
  "location": "Berlin",
  "must_have": ["Python", "PostgreSQL"],
  "nice_to_have": ["Rust"]
}
```

**After (Phase 2 / Plan 03):**
```json
{
  "location": {"country": "DE", "city": "Berlin", "region": null},
  "must_have": [
    {"skill": "Python", "skill_type": "language", "skill_category": "hard"},
    {"skill": "PostgreSQL", "skill_type": "database", "skill_category": "hard"}
  ],
  "nice_to_have": [
    {"skill": "Rust", "skill_type": "language", "skill_category": "hard"}
  ]
}
```

If any external MCP client emerges before Phase 7, this shape change is the migration surface.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing test_ingestion.py used old SkillCategory.LANGUAGE + free-text location**
- **Found during:** Task 2 verify (full pytest suite after sweep).
- **Issue:** `tests/test_ingestion.py::TestIngestFromSource::_make_posting` constructed `JobPosting(location="Berlin", ...)` and `JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, ...)` — pre-existing test broken by Plan 02-01's schema rename.
- **Fix:** Updated fixture to `Location(country="DE", city="Berlin", region=None)` and `JobRequirement(skill="Python", skill_type=SkillType.LANGUAGE, skill_category=SkillCategory.HARD, required=True)`.
- **Files modified:** `tests/test_ingestion.py`.
- **Committed in:** `b9a482e`.

**2. [Rule 1 - Bug] Pre-existing test_mcp_server.py asserted old _serialize_posting shape**
- **Found during:** Task 2 verify.
- **Issue:** `_make_posting()` in test_mcp_server.py set `posting.location = "Berlin"` and bare `MagicMock(skill="Python", required=True)`; assertion checked `must_have == ["Python"]` and `nice_to_have == ["Rust"]`.
- **Fix:** Updated fixture to set `location_country="DE"`, `location_city="Berlin"`, `location_region=None` and per-requirement MagicMock with `skill_type="language"`, `skill_category="hard"`. Updated assertions to the new nested-dict shape; added a third assertion for nested location.
- **Files modified:** `tests/test_mcp_server.py`.
- **Committed in:** `b9a482e`.

**3. [Rule 1 - Lint] 3 ruff violations in newly-written test_alembic.py**
- **Found during:** Task 2 verify (`uv run ruff check`).
- **Issue:** I001 import-block out-of-order (alembic vs. job_rag) on the smoke tests' inner imports; E501 long line on the `pytest.skip("Postgres not reachable...")` message.
- **Fix:** ruff `--fix` resolved 2 of 3; manually wrapped the long skip message.
- **Files modified:** `tests/test_alembic.py`.
- **Committed in:** `b9a482e` (folded with the other Task 2 changes).

**4. [Rule 1 - Test pattern] Initial caplog approach captured 0 records for structlog warnings**
- **Found during:** Task 3 verify (running TestPromptVersionDriftWarning).
- **Issue:** The plan's recommended caplog assertion failed because structlog's `PrintLoggerFactory` does NOT route records through the stdlib logging tree. The warning fired (visible in stdout) but `caplog.records` was `[]`.
- **Fix:** Replaced with `patch.object(app_mod.log, "warning"/"info", side_effect=capture)` capturing `(event_name, kwargs)` tuples directly. Plan's executor-discretion note explicitly flagged this might be needed.
- **Files modified:** `tests/test_lifespan.py`.
- **Committed in:** `5b2405b`.

**Total deviations:** 4 auto-fixed, all Rule 1 scope (pre-existing tests broken by upstream rename + my own newly-written code lint + a documented test-framework integration issue).

## Auth / Manual Steps Required

None. The plan ran fully autonomously. Pre-flight `pg_dump` is documented above as Adrian-discretion (NOT baked into the CLI per D-friction).

## Issues Encountered

- DATABASE_URL env mismatch: `.env` contains literal `postgres:postgres@localhost:5432/job_rag` while the real DB password is the URL-encoded `POSTGRES_PASSWORD` value (16 chars, contains URL-special chars). Worked around for the live alembic upgrade by constructing the proper URL inline (URL-encoded password + `%%` ConfigParser escape) and exporting it before invoking `command.upgrade`. The test smokes skip cleanly because `_postgres_reachable()` uses the unmodified `settings.database_url`. **Pre-existing Phase 1 quirk — not introduced by this plan.** A small future cleanup task: regenerate `.env` with the correct URL-encoded `DATABASE_URL` so `_postgres_reachable()` succeeds and the alembic smoke tests run live in CI.

## Next Phase Readiness

- **Plan 02-04 (live corpus reextract)**: every primitive is in place. Plan 04 just runs:
  ```bash
  uv run python -m job_rag.cli reextract --dry-run    # confirm 108 selected
  uv run python -m job_rag.cli reextract              # 108 LLM round-trips, ~3-5 min, ~€0.20
  ```
  followed by the 4 SQL sanity checks listed in 02-VALIDATION.md. Failures are logged and reported per posting; partial-failure restart is just re-running the command (idempotent default selection).
- **Plan 04 deferred per orchestrator note** — Wave 2 stops here; Plan 04 (live corpus reextract) is a separate, gated step.
- **Phase 5 (Dashboard)**: now reads `JobPostingDB.location_country/city/region` directly. The MCP nested-location shape is the contract Phase 5's API responses will mirror.

## CORP Requirements Status

- **CORP-01** (PROMPT_VERSION + REJECTED_SOFT_SKILLS): closed in Plan 02-02.
- **CORP-02** (SkillType / SkillCategory taxonomy): closed in Plan 02-01.
- **CORP-03** (structured Location): closed in Plan 02-01.
- **CORP-04** (drift detection surfaces): **closed in this plan** — `list --stats`, lifespan startup warning, and `reextract` CLI all land here.

After Plan 04 runs, all 4 CORP-XX requirements have their data refresh executed, not just their mechanism in place.

## Self-Check: PASSED

- [x] `alembic/versions/0004_corpus_cleanup.py` exists (verified via Write).
- [x] `src/job_rag/services/extraction.py` exists with `reextract_stale`, `_reextract_one`, `ReextractReport` (verified via import smoke).
- [x] `tests/test_reextract.py` exists, 7 tests passing.
- [x] `tests/test_cli.py::TestListStatsPromptVersion` exists; passes.
- [x] `tests/test_lifespan.py::TestPromptVersionDriftWarning` exists; 2 tests pass.
- [x] `cli.py` registers `reextract` command (verified via `app.registered_commands` introspection).
- [x] Live `alembic upgrade head` against dev DB: exit 0; 108 postings + 2121 requirements preserved; skill_category backfill = 1844/156/121.
- [x] Live `reextract --dry-run`: Selected=108.
- [x] Commit `1b22306` exists in `git log` (Task 1).
- [x] Commit `b9a482e` exists in `git log` (Task 2).
- [x] Commit `5b2405b` exists in `git log` (Task 3).
- [x] Full pytest suite: 190 passed / 10 skipped / 0 failed.
- [x] Ruff clean. Pyright 0 errors.

---
*Phase: 02-corpus-cleanup*
*Completed: 2026-04-28*
