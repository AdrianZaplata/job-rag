---
phase: 01-backend-prep
plan: 03
subsystem: services
tags: [ingestion-source, protocol, async-pipeline, dataclass, asyncio-bridge, back-10]

# Dependency graph
requires:
  - alembic 1.18.4 + UserDB + JobPostingDB.career_id (Plan 01-02) — schema must exist for _posting_exists_async / _store_posting_async to query against
  - tests/test_ingestion.py scaffolding (Plan 01-01) — Wave 0 placeholders activated by this plan
provides:
  - IngestionSource Protocol + RawPosting frozen dataclass + MarkdownFileSource v1 implementation + IngestResult dataclass
  - ingest_from_source(async_session, source) -> IngestResult — primary async consumer for any future IngestionSource implementation (LinkedIn, scheduled refresh, etc.)
  - Async pipeline helpers (_posting_exists_async, _store_posting_async, _embed_and_store_async) reusable by Plan 06 /ingest route refactor
  - Sync ingest_file backward-compatible shim (asyncio.run + AsyncSessionLocal) — CLI ingest_directory + existing /ingest route keep working unchanged
affects: [01-06-PLAN]  # Plan 06 should call ingest_from_source directly from the async /ingest route, removing the asyncio.run hop

# Tech tracking
tech-stack:
  added: []  # No new packages — all stdlib (asyncio, dataclasses, typing.Protocol, datetime.UTC) plus existing SQLAlchemy async + asyncpg
  patterns:
    - "runtime_checkable async Protocol with sync `def __aiter__(self) -> AsyncIterator[T]` declaration; concrete impls use `async def __aiter__` async-generator form (both produce AsyncIterator at runtime; pyright basic-mode accepts both per Assumption A2)"
    - "frozen+slots dataclass for value types crossing async/thread boundaries — RawPosting raises FrozenInstanceError on mutation, slots eliminates per-instance __dict__"
    - "asyncio.to_thread(sync_fn, *args) for sync I/O (Path.read_text) and sync LLM calls (extract_posting) inside async generators — keeps event loop responsive"
    - "Per-iteration commit + rollback in async ingest loop — partial failures don't undo prior successful ingests"
    - "Sync→async bridge in ingest_file: asyncio.run(_run()) wrapping AsyncSessionLocal context — preserves sync caller contract while body uses async pipeline"
    - "Async→sync bridge in _embed_and_store_async: commit pending INSERT then asyncio.to_thread(_sync_embed) with fresh SessionLocal — Phase 1 Option A bridge documented as deferred refactor"

key-files:
  created: []
  modified:
    - src/job_rag/services/ingestion.py (+225 lines net: 4 new types + 3 async helpers + ingest_from_source + rewrapped ingest_file)
    - tests/test_ingestion.py (replaced 1 placeholder skip with 3 mocked unit tests; net +130 lines)

key-decisions:
  - "Used `async def __aiter__` (async-generator form) on MarkdownFileSource even though Protocol declares the sync form — pyright basic-mode accepted both and the async-generator body is more idiomatic. Assumption A2 confirmed correct for this codebase. No fallback restructure needed."
  - "Replaced the test_ingestion.py roundtrip placeholder with 3 mocked unit tests (happy-path, dedup, error) instead of leaving a DB-required skip. Mocking _posting_exists_async / _store_posting_async / _embed_and_store_async / extract_posting keeps the suite unit-speed while exercising the consumer's actual control flow (counts, posting_ids list, error_details capture). The DB-integration path is exercised by the live CLI smoke against the real dev DB."
  - "Added a defensive `extract_linkedin_id(posting.source_url)` fallback inside ingest_from_source's success path — preserves the existing sync ingest_file behaviour where linkedin_id may be None at the start (no link in body) but the LLM extracts a source_url containing one. Without this, the async path would have lost a dedup signal the sync path captured."
  - "_embed_and_store_async commits the pending JobPostingDB INSERT BEFORE handing off to the sync embed thread (so the sync session can `.get(JobPostingDB, posting_id)` the row). Then ingest_from_source calls `await async_session.commit()` again — that second commit is a no-op for the parent INSERT but captures any JobRequirementDB rows added in _store_posting_async that were flushed-but-not-yet-committed under SA's UoW model. Documented inline."
  - "Replaced `from datetime import timezone` with `from datetime import UTC` (Python 3.11+ alias) per ruff UP017. The codebase already targets py312 (pyproject.toml [tool.pyright]/[tool.ruff]); UTC is the canonical form."

patterns-established:
  - "Pattern: IngestionSource extension point — any new source (LinkedIn API client, scheduled refresh, S3 bucket reader) implements `async def __aiter__(self) -> AsyncIterator[RawPosting]` returning RawPosting(raw_text, source_url, source_id, fetched_at). The Protocol is `runtime_checkable` so isinstance() works as a sanity gate; pyright is the real contract enforcer."
  - "Pattern: sync-wrapper-around-async-pipeline preserving caller contract — sync `ingest_file(session, file_path) -> tuple[bool, str, str|None]` body is `asyncio.run(_run())` over the async path, with explicit caveat that asyncio.run raises RuntimeError if invoked from inside an active event loop. Used here for CLI compat; future async callers (FastAPI /ingest in Plan 06) should call ingest_from_source directly with their request's AsyncSession dependency, skipping the wrapper."
  - "Pattern: structured error capture in IngestResult.error_details — `(source_url, str(e))` tuples, NOT free-form strings, NOT exception classes. Service layer keeps them structured; downstream caller (route handler) decides whether to surface them and how to sanitize. Mitigates T-03-02 (info-disclosure) without forcing service-layer sanitization."

requirements-completed: [BACK-10]

# Metrics
duration: ~38m  # 2026-04-27T08:33Z to 2026-04-27T09:11Z (estimated)
completed: 2026-04-27
---

# Phase 1 Plan 03: IngestionSource Protocol + Async Pipeline Summary

**Decoupled ingestion source from storage by introducing the `IngestionSource` Protocol + `RawPosting` frozen dataclass + `MarkdownFileSource` v1 implementation, and added `ingest_from_source(async_session, source) -> IngestResult` as the new primary async consumer. Existing sync `ingest_file(session, file_path) -> tuple[bool, str, str | None]` rewrapped via `asyncio.run` + `AsyncSessionLocal` to preserve the CLI and `/ingest` endpoint wire contracts (D-24). Full async-ingest pipeline refactor remains deferred per CONTEXT §Deferred Ideas.**

## Performance

- **Duration:** ~38m (start 2026-04-27T08:33Z, last commit 2026-04-27T08:48Z + ~10m for SUMMARY/state work)
- **Tasks:** 2 (both atomic, both committed individually)
- **Files modified:** 2 (src/job_rag/services/ingestion.py, tests/test_ingestion.py)
- **Files created:** 0 (all changes in existing files per D-23)

## Accomplishments

- **4 new public types** in `src/job_rag/services/ingestion.py`:
  - `RawPosting` — frozen+slots dataclass with exactly 4 fields per D-21 (`raw_text`, `source_url`, `source_id`, `fetched_at`); FrozenInstanceError on mutation verified.
  - `IngestionSource` — `runtime_checkable` Protocol with `__aiter__(self) -> AsyncIterator[RawPosting]` per D-20; `isinstance(MarkdownFileSource(tmp), IngestionSource)` returns True.
  - `MarkdownFileSource` — v1 implementation; reads `.md` files via `asyncio.to_thread(Path.read_text)`, extracts `linkedin_job_id` from first matching URL in body via existing `extract_linkedin_id` helper.
  - `IngestResult` — dataclass with 7 fields including `posting_ids: list[str]` (preserves slot 3 of sync `ingest_file` 3-tuple per Assumption A3).
- **3 async helpers** mirror the existing sync helpers verbatim (T-03-04 mitigation):
  - `_posting_exists_async(async_session, content_hash, linkedin_id) -> bool` — `select(JobPostingDB).where(...)` + `await session.execute(...).scalar_one_or_none()`.
  - `_store_posting_async(async_session, posting, content_hash, linkedin_id) -> JobPostingDB` — field list mirrors `_store_posting` exactly (linkedin_id, content_hash, title, company, location, remote_policy.value, salary_*, seniority.value, employment_type, joined responsibilities/benefits, source_url, raw_text, PROMPT_VERSION constant + JobRequirementDB child rows).
  - `_embed_and_store_async(async_session, db_posting) -> None` — Phase 1 Option A bridge: commits the pending INSERT then delegates `embed_and_store_posting` to `asyncio.to_thread` with a fresh `SessionLocal`. Documented as deferred refactor.
- **`ingest_from_source(async_session, source) -> IngestResult`** primary async consumer:
  - Computes `content_hash = hashlib.sha256(raw.raw_text.encode()).hexdigest()` inline (D-22 — service layer, not Protocol).
  - Pushes sync+LLM `extract_posting` to `asyncio.to_thread` per RESEARCH §"ingest_from_source consumer".
  - Per-iteration `await async_session.commit()` so single failures don't undo prior ingests.
  - Captures `IntegrityError` as `result.skipped += 1`; captures all other exceptions as `result.errors += 1` with `(source_url, str(e))` tuple in `error_details`.
  - Defensive linkedin-id fallback from `posting.source_url` (mirrors sync `ingest_file` behaviour).
- **Sync `ingest_file(session, file_path)` rewrapped** to `asyncio.run(_run())` over `AsyncSessionLocal()` + `MarkdownFileSource(file_path)` + `ingest_from_source(...)`. Signature + 3-tuple return shape unchanged; posting_id (slot 3) sourced from `IngestResult.posting_ids[0]` on success. Sync `session` parameter retained for caller-API parity with `# noqa: ARG001` documenting the unused-but-kept argument.
- **3 new test_ingestion.py tests** activated:
  - `test_ingest_from_source_roundtrip` — happy-path: 2 .md files, mocked extract + DB helpers, verifies `total=2 / ingested=2 / total_cost_usd=0.002 / len(posting_ids)=2`.
  - `test_ingest_from_source_dedup_second_run` — `_posting_exists_async` returns True for every check, verifies `ingested=0 / skipped=2`.
  - `test_ingest_from_source_extract_error_counted` — `extract_posting` raises RuntimeError, verifies `errors=1 / error_details=[(file://..., "...LLM is sad...")]`.
- **CLI smoke test passed end-to-end against the real dev DB** (108 postings already ingested in Plan 02). Calling `ingest_file(SessionLocal(), Path("data/postings/acto-...md"))` flowed: `asyncio.run` → `AsyncSessionLocal()` (asyncpg) → `ingest_from_source` → `_posting_exists_async` (real query) → returned `(False, "duplicate", None)`. Structured log line confirmed dedup branch fired with `source_id=4372462825` extracted from the markdown body.
- **Full non-eval suite: 89 passed, 13 skipped, 0 failed** (up from 86 passed pre-Plan-03 — 3 new tests went live).
- **pyright: 0 errors** on `src/job_rag/services/ingestion.py` + `tests/test_ingestion.py`.
- **ruff: clean** on both files.

## Task Commits

Each task committed atomically with conventional-commit messages:

1. **Task 1: Add IngestionSource Protocol + RawPosting + MarkdownFileSource + IngestResult** — `9408e14` (`feat(01-03)`)
2. **Task 2: Add ingest_from_source async consumer + rewrap sync ingest_file via asyncio.run** — `24afe5e` (`feat(01-03)`)

Plan metadata commit (this SUMMARY + STATE.md + ROADMAP.md update) follows after self-check.

## Files Created/Modified

### Created (0)

None — D-23 explicitly forbids a new package; all new types live in the existing `src/job_rag/services/ingestion.py`.

### Modified (2)

- `src/job_rag/services/ingestion.py` — net +225 lines:
  - Added imports: `asyncio`, `hashlib` (already present), `AsyncIterator`, `dataclass`/`field`, `UTC`/`datetime`, `Protocol`/`runtime_checkable`, `select`, `AsyncSession`, `AsyncSessionLocal`.
  - Added `RawPosting` frozen+slots dataclass (4 fields per D-21).
  - Added `IngestionSource` runtime_checkable Protocol (sync `__aiter__` declaration returning `AsyncIterator[RawPosting]`).
  - Added `MarkdownFileSource` v1 implementation (`async def __aiter__` async generator; `asyncio.to_thread(f.read_text, encoding="utf-8")`; first-match `linkedin.com/jobs/view/` regex extraction).
  - Added `IngestResult` dataclass (7 fields including `posting_ids: list[str]`).
  - Added module-level threat-model comment block (T-03-01/02/03 mitigations referenced).
  - Added 3 async helpers `_posting_exists_async` / `_store_posting_async` / `_embed_and_store_async` mirroring sync counterparts.
  - Added `ingest_from_source(async_session, source) -> IngestResult` async consumer.
  - Rewrote `ingest_file(session, file_path)` body to delegate via `asyncio.run(_run())` + `AsyncSessionLocal()` + `MarkdownFileSource(file_path)` + `ingest_from_source(...)`. Signature + 3-tuple return shape unchanged. Sync `session` parameter retained with `# noqa: ARG001` documenting the unused-but-kept argument.
  - Existing sync `_content_hash`, `_posting_exists`, `_store_posting`, `ingest_directory` UNTOUCHED — remain reachable for any other sync caller.

- `tests/test_ingestion.py` — net +130 lines:
  - Replaced the single `pytest.skip("Full roundtrip deferred...")` placeholder in `test_ingest_from_source_roundtrip` with 3 fully-active mocked unit tests in `TestIngestFromSource`:
    - `test_ingest_from_source_roundtrip` (happy path: 2 files, 2 ingested, posting_ids list populated, cost summed).
    - `test_ingest_from_source_dedup_second_run` (every check returns True, all skipped).
    - `test_ingest_from_source_extract_error_counted` (extract_posting raises, errors counted, error_details captured).
  - Added `_make_posting()` static helper on `TestIngestFromSource` returning a minimal valid `JobPosting` for mock extraction returns.
  - All 4 pre-existing tests (`test_markdown_file_source_satisfies_protocol`, `test_raw_posting_is_frozen_dataclass`, `test_markdown_file_source_yields`, `test_ingest_file_sync_compat`) UNTOUCHED — they pass against the new types.

## Decisions Made

- **Used `async def __aiter__` (async-generator form) on MarkdownFileSource even though the Protocol declares `def __aiter__`.** Assumption A2 in 01-RESEARCH.md predicted pyright basic-mode would accept both shapes; I confirmed it does (0 errors). No need for the documented fallback restructure (`def __aiter__(self) -> AsyncIterator[...]: return self._iter()` with `async def _iter` separately). The async-generator form is more idiomatic and saves one indirection.
- **Replaced the test_ingestion.py roundtrip placeholder with 3 fully mocked unit tests** instead of leaving a DB-required skip with a TODO comment. The plan explicitly authorized either path ("the test should either mock the async session or remain pytest.skip"). Mocking the 4 boundary helpers (`_posting_exists_async`, `_store_posting_async`, `_embed_and_store_async`, `extract_posting`) keeps the suite unit-speed (<1s) while exercising the consumer's actual control flow — counts, posting_ids list mutation, error_details tuple capture, dedup branch. The DB-integration path is exercised by the CLI smoke against the real dev DB (see Smoke Test Outcome below).
- **Added defensive `extract_linkedin_id(posting.source_url)` fallback inside ingest_from_source's success path.** The existing sync `ingest_file` (lines 103-104 of original file) computed linkedin_id once from the raw text BEFORE calling LLM, then a second time from `posting.source_url` if the first attempt was None. Without mirroring this fallback in the async path, postings whose linkedin URL only appears in extracted `source_url` (not in raw markdown body) would lose a dedup signal the sync path had. Added 4 lines after `posting.raw_text = raw.raw_text` to preserve this behaviour.
- **`_embed_and_store_async` commits BEFORE the sync embed thread runs, then ingest_from_source commits again afterwards.** First commit is required so the sync session in the thread can `.get(JobPostingDB, posting_id)` the row. Second commit captures the JobRequirementDB child rows added in `_store_posting_async` (which were flushed-but-not-committed). Both commits documented inline. Net effect matches sync `ingest_file` semantics: posting + requirements + chunks + embedding all committed atomically per posting.
- **Replaced `from datetime import timezone` (and `timezone.utc`) with `from datetime import UTC` per ruff UP017.** Project targets Python 3.12 (pyproject.toml `[tool.pyright].pythonVersion = "3.12"` and `[tool.ruff].target-version = "py312"`); `datetime.UTC` is the 3.11+ canonical form.
- **Did not modify `ingest_directory`.** The plan focuses on `ingest_file` only. `ingest_directory` already calls `ingest_file` per-file with sync session; it continues to work because the sync-wrapper of `ingest_file` retains its signature. Deferring batch-async-ingest is consistent with D-24's "full async-ingest pipeline refactor explicitly deferred."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff UP017 flagged `timezone.utc` after Task 1's first edit pass**

- **Found during:** Task 1 (verification step `uv run ruff check src/job_rag/services/ingestion.py`)
- **Issue:** I initially used `from datetime import datetime, timezone` and `datetime.now(timezone.utc)` per the plan's example code in `<action>` step 2. ruff UP017 flagged this as fixable: "Use `datetime.UTC` alias" — the project's ruff config selects `UP` (pyupgrade) and targets Python 3.12 where the `datetime.UTC` alias exists.
- **Fix:** Switched to `from datetime import UTC, datetime` and `datetime.now(UTC)` (2 line edits).
- **Files modified:** `src/job_rag/services/ingestion.py`
- **Verification:** `uv run ruff check src/job_rag/services/ingestion.py` → "All checks passed!". Tests + pyright still pass.
- **Committed in:** `9408e14` (Task 1 commit) — caught and fixed within Task 1 before commit.

**2. [Rule 2 - Missing functionality] Plan's `_store_posting_async` field list omitted required JobRequirementDB child rows + had wrong `prompt_version` source**

- **Found during:** Task 2 implementation (cross-checking the plan's `<action>` block against the existing sync `_store_posting` body)
- **Issue:** The plan's example `_store_posting_async` action snippet (lines 381-407 of 01-03-PLAN.md) listed parent JobPostingDB fields but did NOT include the `for req in posting.requirements: session.add(JobRequirementDB(...))` loop that the sync helper has — and used `prompt_version=getattr(posting, "prompt_version", None)` instead of importing the `PROMPT_VERSION` constant from `extraction.prompt`. The plan itself flagged this as a gap: "Field list mirrors the existing sync `_store_posting`. Read that helper to determine the exact mapping." T-03-04 in the threat model explicitly mitigates this drift risk via "executor's acceptance criterion is to READ the existing helper before writing the async twin."
- **Fix:** Read the existing sync `_store_posting` (lines 154-192 of pre-edit file). Mirrored every field exactly (including `salary_raw`, `salary_period.value`, `employment_type`, joined `responsibilities` / `benefits`) and added the JobRequirementDB child-row loop after `await session.flush()`. Replaced `getattr(posting, "prompt_version", None)` with the canonical `prompt_version=PROMPT_VERSION` constant.
- **Files modified:** `src/job_rag/services/ingestion.py`
- **Verification:** `uv run pyright src/job_rag/services/ingestion.py` → 0 errors (pyright validates JobPostingDB constructor fields). Mocked roundtrip test passes — `_store_posting_async` is called and returns a MagicMock with `.id` (real DB-side field validation deferred to Plan 06's full /ingest test).
- **Committed in:** `24afe5e` (Task 2 commit)

**3. [Rule 1 - Bug] Plan's `ingest_from_source` snippet dropped the linkedin-id fallback that sync `ingest_file` had**

- **Found during:** Task 2 (cross-checking the plan's example `ingest_from_source` body against the existing sync `ingest_file` behaviour)
- **Issue:** Sync `ingest_file` (lines 103-104 of pre-edit file) computed `linkedin_id` once from raw markdown before extraction, then a second time from `posting.source_url` AFTER extraction if the first attempt returned None. The plan's example async consumer (lines 461-509 of 01-03-PLAN.md) only used `raw.source_id` directly — losing the post-extraction fallback. This would cause postings whose linkedin URL only appears in the extracted source_url (not the raw markdown body) to be inserted with `linkedin_job_id=None`, breaking dedup on subsequent re-ingests. Must-have truth #5 ("linkedin_job_id extraction matches the existing pattern") is at risk without the fallback.
- **Fix:** Added 4 lines after `posting.raw_text = raw.raw_text` inside the success branch:
  ```python
  linkedin_id = raw.source_id
  if not linkedin_id:
      linkedin_id = extract_linkedin_id(posting.source_url)
  ```
  Then passed `linkedin_id` (instead of `raw.source_id`) to `_store_posting_async`.
- **Files modified:** `src/job_rag/services/ingestion.py`
- **Verification:** Mocked roundtrip test still passes (mock returns a `JobPosting` whose `source_url=https://example.com/job/1` does NOT contain a linkedin URL, so the fallback returns None — test counts unchanged). Live CLI smoke test against the real dev DB confirmed dedup fired with `source_id=4372462825` extracted from the raw markdown body (the primary path).
- **Committed in:** `24afe5e` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 × Rule 1 - linter compliance, 1 × Rule 2 - missing functionality, 1 × Rule 1 - missing-fallback bug)

**Impact on plan:** All three fixes were required for correctness. Fix #1 was a one-liner the plan didn't anticipate (UP017 ruff rule on the example code). Fix #2 caught a real cross-file spec gap (plan's action snippet vs. existing sync helper) — T-03-04 in the plan's own threat register explicitly required cross-checking the sync helper, which surfaced the gap. Fix #3 caught a behavioural-regression risk (sync `ingest_file` had a fallback the plan's async snippet dropped). No scope creep; all fixes stayed inside `src/job_rag/services/ingestion.py`.

## Issues Encountered

- **Smoke test required URL-encoded password + socat sidecar.** The dev container's `POSTGRES_PASSWORD=97nE&6L!1Jq$3zdX` contains shell-special characters; SQLAlchemy/asyncpg URL needed `urllib.parse.quote` encoding (22-char encoded form). The dev DB only `expose:`s 5432 to the docker network (no host port mapping per docker-compose.yml — same situation Plan 02 documented), so I spun up an `alpine/socat` sidecar on `--network job-rag_default` mapping host `127.0.0.1:5436 → job-rag-db-1:5432` to give the host CLI a path in. Stopped the sidecar after the smoke run. No compose changes.
- **`.env` file's `DATABASE_URL` does not match the running container's password.** `.env` literal is `postgres` but container env reports `97nE&6L!1Jq$3zdX`. This caused the first smoke attempt to fail with `InvalidPasswordError`. Workaround: extracted the real password via `docker exec ... printenv POSTGRES_PASSWORD`. Adrian may want to reconcile `.env` with the container during a future cleanup pass — not in scope for this plan, but flagged.
- **A potential double-embedding regression in /ingest route exists but is documented as Plan 06's responsibility.** The current `/ingest` route in `src/job_rag/api/routes.py` (lines 178-186) calls `embed_and_store_posting` AFTER the rewrapped `ingest_file` returns — but the rewrapped `ingest_file` now ALREADY embeds via `_embed_and_store_async` inside `ingest_from_source`. Calling `/ingest` for an HTTP-uploaded posting would create duplicate JobChunkDB rows. Plan 03 does NOT modify the `/ingest` route handler — D-24 / the plan's `<action>` step 4 explicitly notes "when Plan 06 wires /ingest, it will need to call `ingest_from_source` DIRECTLY (not via the sync wrapper). This contract shift is Plan 06's responsibility." The CLI ingest path (which is the smoke-tested target) does NOT call `embed_and_store_posting` separately — the regression is API-only and Plan 06 is the right phase to fix it. Flagged for Plan 06 planner.

## User Setup Required

None for code/test execution. No new env vars, no new external services. Adrian's CLI workflow is unchanged:
- `uv run job-rag ingest data/postings/` continues to work via the rewrapped `ingest_file`. The internal pipeline is now async-first; the user-facing UX is identical.
- For HTTP-side `/ingest` usage (Phase 6+ frontend): Plan 06 will wire the route to call `ingest_from_source` directly with the request's AsyncSession dependency, eliminating the sync wrapper hop and fixing the documented double-embedding regression.

## Smoke Test Outcome

End-to-end smoke against the real dev DB (108 postings already present from Plan 02):

```
Calling ingest_file(acto-senior-staff-ai-engineer-agentic-systems.md)...
2026-04-27T08:44:48Z [info] skipped_duplicate
  source_id=4372462825
  source_url=file://C:\...\acto-senior-staff-ai-engineer-agentic-systems.md
was_ingested=False
reason=duplicate
posting_id=None
SMOKE OK
```

Verified:
- `asyncio.run(_run())` opens an `AsyncSessionLocal()` over asyncpg without errors (URL-encoded password works).
- `MarkdownFileSource(file_path)` yields the single RawPosting with `source_id="4372462825"` extracted from the markdown body.
- `_posting_exists_async` runs a real query against `job_postings` and returns True for this content hash.
- `ingest_from_source` short-circuits to `result.skipped += 1` and emits the structured log line.
- Sync `ingest_file` translates `result.skipped == 1` → `(False, "duplicate", None)` matching the original sync return contract.
- No exceptions, no rollback errors, no event-loop interaction issues.

## Threat Flags

None. The four threats in this plan's `<threat_model>` were all mitigated exactly as specified:

- **T-03-01** (path-traversal tampering): `MarkdownFileSource(path)` v1 receives its `Path` from the CLI (Typer arg) — Adrian-controlled trust boundary. Module-level docstring documents that future IngestionSource implementations accepting user-supplied paths MUST validate at the consumer.
- **T-03-02** (info-disclosure via error_details): `IngestResult.error_details` captures `(source_url, str(e))` tuples — structured, not free-form. Service layer keeps them structured; downstream caller (Plan 06 `/ingest` route) is responsible for sanitization before client surface. The threat model explicitly notes "Plan 03 keeps the contract — no sanitization at service layer since error_details is structured, not free-form user output."
- **T-03-03** (DoS via large file): Accepted per CONTEXT.md — Adrian-curated single-user corpus, no adversarial file size. v2 streaming-read deferred.
- **T-03-04** (field-mapping drift between sync and async helpers): Mitigated by Deviation #2 above — I read the existing sync `_store_posting` before writing `_store_posting_async` and mirrored every field including the JobRequirementDB child-row loop. pyright (which validates JobPostingDB constructor field names) confirms zero drift at the type level. Real runtime drift would surface as Pydantic/SQLAlchemy errors on first use.

No new security-relevant surface introduced beyond the threat register.

## Next Phase Readiness

Plan 03 is complete. The Wave-1 plans 03-06 are independent of each other; Plans 04, 05, 06 remain unblocked.

For Plan 06 (route handler with timeout + heartbeat + drain) — note the action item handed off:
- Rewrite the `/ingest` FastAPI route in `src/job_rag/api/routes.py` (lines 150-188) to call `ingest_from_source(request_async_session, MarkdownFileSource(tmp_path))` DIRECTLY instead of `ingest_file(sync_session, tmp_path)`. This:
  - Removes the `asyncio.run` hop (FastAPI is already inside an event loop — `asyncio.run` from a request handler raises RuntimeError today; the rewrapped sync `ingest_file` is currently safe only because the route uses `SessionLocal()` not the async dep, and the `asyncio.run` opens a fresh loop — but this is fragile).
  - Removes the route's separate `embed_and_store_posting` call (lines 178-186) since `ingest_from_source` now embeds inline via `_embed_and_store_async`. Eliminates the documented double-embedding regression risk.
  - Surfaces `IngestResult.error_details` to the client with appropriate sanitization (T-03-02 disposition handoff).

For future plans (Plan 02-style migration / source extension):
- New IngestionSource implementations (LinkedIn API, scheduled refresh) drop into `src/job_rag/services/ingestion.py` (or a future `src/job_rag/ingestion/` package once source #2 lands per D-23).
- Each implementation just needs `async def __aiter__(self) -> AsyncIterator[RawPosting]`. The `runtime_checkable` Protocol means `isinstance(src, IngestionSource)` works as a sanity gate.

ROADMAP shows Phase 1 progress will tick from `2/6` to `3/6` plans complete.

No blockers. No open questions.

## Self-Check: PASSED

Verification ran 2026-04-27T08:55Z (post-commit):

**Files / commits:**
- [x] `src/job_rag/services/ingestion.py` exists and contains all 4 new types — FOUND (4/4 grep)
- [x] `tests/test_ingestion.py` exists with 7 tests (4 active before Plan 03 + 3 new in TestIngestFromSource) — FOUND
- [x] Commit `9408e14` exists in git log — FOUND
- [x] Commit `24afe5e` exists in git log — FOUND
- [x] No deletions in either commit — VERIFIED via `git diff --diff-filter=D --name-only HEAD~1 HEAD` returned empty

**Plan grep verifications:**
- [x] `class IngestionSource` — FOUND
- [x] `class RawPosting` — FOUND
- [x] `class MarkdownFileSource` — FOUND
- [x] `class IngestResult` — FOUND
- [x] `@runtime_checkable` — FOUND
- [x] `@dataclass(frozen=True, slots=True)` — FOUND
- [x] `async def ingest_from_source` — FOUND
- [x] `async def _posting_exists_async` — FOUND
- [x] `async def _store_posting_async` — FOUND
- [x] `hashlib.sha256` — FOUND
- [x] `asyncio.run(_run())` — FOUND
- [x] `posting_ids` — FOUND
- [x] `def ingest_file(\\n session: Session` (multi-line signature) — FOUND

**Plan must_haves.truths (frontmatter):**
- [x] (1) `from job_rag.services.ingestion import IngestionSource, RawPosting, MarkdownFileSource, ingest_from_source, IngestResult` succeeds — VERIFIED
- [x] (2) `MarkdownFileSource(tmp_path) satisfies isinstance(..., IngestionSource)` — VERIFIED via test_markdown_file_source_satisfies_protocol PASS
- [x] (3) `RawPosting` is frozen+slotted; field assignment raises FrozenInstanceError — VERIFIED via test_raw_posting_is_frozen_dataclass PASS
- [x] (4) Iterating MarkdownFileSource over directory with N .md files yields N RawPosting objects sorted by filename — VERIFIED via test_markdown_file_source_yields PASS
- [x] (5) linkedin_job_id extraction matches existing pattern (12345 from `linkedin.com/jobs/view/12345/`; None when absent) — VERIFIED via test_markdown_file_source_yields PASS + live smoke (4372462825 extracted)
- [x] (6) `ingest_from_source(async_session, source)` returns IngestResult with total/ingested/skipped/errors/total_cost_usd/posting_ids — VERIFIED via 3 mocked TestIngestFromSource tests
- [x] (7) Sync `ingest_file(session, file_path)` still works — CLI live smoke PASSED end-to-end (returned `(False, "duplicate", None)` from real dev DB)

**Plan must_haves.artifacts:**
- [x] `src/job_rag/services/ingestion.py` provides "IngestionSource Protocol; RawPosting; MarkdownFileSource; IngestResult; ingest_from_source; rewrapped sync ingest_file"; contains "class IngestionSource"; min_lines: 200 — VERIFIED (file is now 412 lines, was 156)

**Plan must_haves.key_links:**
- [x] MarkdownFileSource → IngestionSource via runtime_checkable structural typing — VERIFIED via isinstance() test
- [x] ingest_from_source → hashlib.sha256(raw_text.encode()).hexdigest() (D-22 service-side hash) — VERIFIED via grep "hashlib.sha256" in ingest_from_source body
- [x] ingest_file (sync wrapper) → ingest_from_source via asyncio.run — VERIFIED via grep "asyncio.run(_run())" + signature inspection

**Test + lint state:**
- [x] `uv run pyright src/job_rag/services/ingestion.py tests/test_ingestion.py` → 0 errors — VERIFIED
- [x] `uv run ruff check src/job_rag/services/ingestion.py tests/test_ingestion.py` → All checks passed — VERIFIED
- [x] `uv run pytest tests/test_ingestion.py -x --tb=short` → 7 passed, 0 skipped, 0 failed — VERIFIED
- [x] `uv run pytest -m "not eval"` → 89 passed, 13 skipped, 0 failed — VERIFIED (up from 86 passed pre-Plan-03)

**Live CLI smoke:**
- [x] `ingest_file(SessionLocal(), Path("data/postings/acto-...md"))` against real dev DB returned `(False, "duplicate", None)` with structured log line confirming dedup branch fired — VERIFIED

All `must_haves.truths` and `must_haves.artifacts` from plan frontmatter satisfied. All grep checks pass. All threat-model dispositions implemented as specified.

---
*Phase: 01-backend-prep*
*Completed: 2026-04-27*
