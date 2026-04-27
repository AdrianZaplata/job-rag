---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Phase 01 complete — ready for Phase 02
last_updated: "2026-04-27T11:51:27.963Z"
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 6
  completed_plans: 6
  percent: 100
---

# State: job-rag web-app milestone

**Initialized:** 2026-04-23
**Last updated:** 2026-04-27

## Project Reference

- **Core value**: Make Adrian's job-market corpus actually usable for his Berlin AI-Engineer job hunt (browse it, question it, measure his CV against it) while doubling as a portfolio artefact mapping to concrete Azure / MLOps / SQL gap-fill items.
- **Project doc**: `.planning/PROJECT.md`
- **Requirements doc**: `.planning/REQUIREMENTS.md`
- **Roadmap doc**: `.planning/ROADMAP.md`
- **Research**: `.planning/research/SUMMARY.md`, `STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `FEATURES.md`
- **Codebase map**: `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `CONCERNS.md`

## Current Focus

Phase 1 (Backend Prep) **COMPLETE**. All 6 plans landed; verifier returned `status: passed (5/5 must-haves)`. The backend now ships CORSMiddleware (env allowlist, never `*`), Pydantic-typed SSE event contract exposed in OpenAPI, FastAPI lifespan with reranker preload + SIGTERM drain (30s budget) + asyncio.to_thread reranker wraps, `/agent/stream` with sse-starlette ping heartbeats + asyncio.timeout(60s) + sanitized error frames + cooperative shutdown drain, `get_current_user_id` Depends() injected on `/match` `/gaps` `/ingest` (returns `settings.seeded_user_id` — Phase 4 rewrites body for Entra JWT), Alembic as the canonical schema path (3 migrations, init_db wraps `alembic upgrade head`, dev DB transitioned losslessly with 108 postings preserved + career_id backfilled + seed user inserted), and IngestionSource Protocol with MarkdownFileSource v1 + ingest_from_source async consumer. CI gained postgres service container + alembic upgrade smoke step + user_id DEFAULT grep guard. All 10 BACK-* requirements closed.

## Current Position

Phase: 01 (backend-prep) — COMPLETE
Next: Phase 02 (Corpus Cleanup) or Phase 03 (Infrastructure & CI/CD) — both unblocked per ROADMAP parallelization notes

- **Phase**: 1 - Backend Prep — verified passed (5/5 must-haves)
- **Plan**: All 6 plans complete with SUMMARY.md files; VERIFICATION.md created
- **Status**: 111 passed / 1 skipped / 0 failed; ruff clean; pyright 0 errors; CI workflow YAML structurally valid; all 10 BACK-* requirements closed
- **Progress**: 1/8 phases complete; 6/6 Phase 1 plans complete (100%)

```
[x] Phase 1: Backend Prep                    ✓ COMPLETE
[ ] Phase 2: Corpus Cleanup                  <- next (parallel-eligible with 3)
[ ] Phase 3: Infrastructure & CI/CD          <- next (parallel-eligible with 2)
[ ] Phase 4: Frontend Shell + Auth
[ ] Phase 5: Dashboard
[ ] Phase 6: Chat
[ ] Phase 7: Profile & Resume Upload
[ ] Phase 8: Eval & Documentation
```

## Performance Metrics

| Metric | Value |
|--------|-------|
| v1 requirements | 67 |
| Requirements mapped | 67 (100%) |
| Requirements unmapped | 0 |
| Phases planned | 8 |
| Phases complete | 1 |
| Plans complete | 6 |

### Per-Plan Execution

| Plan | Duration | Tasks | Files | Commits |
|------|----------|-------|-------|---------|
| 01-01 (Wave 0 foundation)              | 13m 42s | 2 | 12 | 246caad, 64345d0 |
| 01-02 (Alembic adoption)               | ~28m    | 2 | 9  | 55212c5, 56307f4 |
| 01-03 (IngestionSource Protocol)       | n/a     | 2 | n/a| 9408e14, 24afe5e |
| 01-04 (SSE Pydantic event contract)    | 11m 24s | 2 | 6  | 6ba420d, 35f2bbe |
| 01-05 (lifespan + CORS + auth dep)     | 8m 6s   | 2 | 5  | e968969, ab0657e |

## Accumulated Context

### Decisions (from execution — Phase 1)

- **Plan 01-01:** Use `Annotated[list[str], NoDecode]` from `pydantic_settings` for env-CSV list fields — bypasses Pydantic Settings 2.x default JSON-decode-first behavior on complex types so the `field_validator(mode="before")` sees the raw CSV string. Pattern reusable for any future env-list field.
- **Plan 01-01:** Wave 0 test scaffolding pattern — each test guards three failure modes (`ImportError` on module, `AttributeError` on `mock.patch` target, `hasattr` check on referenced symbol) so all scaffolding tests skip cleanly and activate the moment downstream plans land their target symbols. No test edits needed when downstream plans complete.
- **Plan 01-01:** Use `importlib.import_module()` + `hasattr()` for forward-reference imports in tests (cleaner than scattered `# pyright: ignore` comments; satisfies pyright basic-mode and ruff I001 simultaneously).
- **Plan 01-02:** Three-migration baseline split (0001 = pre-Phase-1 schema, 0002 = users + user_profile + seed, 0003 = career_id) instead of one all-up baseline. Required because dev DB has only the pre-Phase-1 3-table schema; stamping at 'head' would skip 0002+0003 creation. Splitting lets dev stamp at 0001 and apply 0002+0003 cleanly. Lossless transition for 108 dev postings.
- **Plan 01-02:** Use `server_default=` (not Python-side `default=`) on UserProfileDB string columns to match migration DDL exactly. Plan PATTERNS.md spec disagreed across files. server_default ensures `alembic check` reports zero drift (must-have truth #7) and DDL defaults apply to non-ORM INSERTs (admin tooling future-proof). user_id remains NO default per D-12 invariant.
- **Plan 01-02:** Use direct `INSERT INTO alembic_version` + socat sidecar for dev DB stamp/upgrade instead of `alembic stamp 0001`. Adrian's dev DB password contains `&%!$` which require URL-encoding; alembic.config.set_main_option uses ConfigParser interpolation that chokes on `%` in the encoded password. Direct SQL bypasses the parser; future migrations on dev use `DATABASE_URL='...%%26...'` with `%%` escaped.
- **Plan 01-02:** pgvector + Alembic env.py pattern — `connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector` MUST run BEFORE `context.configure()`. Pitfall A. Without it autogenerate sees embedding columns as sa.NullType and produces broken migrations.
- **Plan 01-04:** Use `X | Y` syntax over `Union[X, Y]` for the AgentEvent discriminated union — required by ruff UP007 (selected in `[tool.ruff.lint] select = ["E","F","I","UP"]`) and supported by Pydantic v2's discriminated-union machinery as the inner type of `Annotated[..., Field(discriminator="type")]`. Verified via 8 passing roundtrip tests + OpenAPI introspection. Plan author's interfaces block predated the project's ruff config check.
- **Plan 01-04:** Pattern: `to_sse(event)` helper as the central conversion from Pydantic event to `{event: type, data: model_dump_json()}` for sse-starlette. Route handlers stay thin (Plan 06 just iterates + calls `to_sse`); event semantics live in the Pydantic model classes. Reusable for any future SSE contracts (e.g., admin event bus).
- **Plan 01-04:** Wave 0 scaffold guard widening pattern — when a Wave 0 test scaffold's skip-guard only checks for module presence (Plan 04 lands `sse.py`) but the assertion needs a downstream wiring (Plan 06 wires `components.schemas`), widen the guard with a content-presence check + descriptive skip message. Preserves test intent ("activate the moment either lands") without needing test edits when the next plan ships.
- **Plan 01-04:** Pattern: `.planning/phases/XX-name/deferred-items.md` log per phase — when a refactor breaks code outside the plan's stated files but ANOTHER plan in the same phase will rewrite that code anyway (e.g., `routes.py:143` deferred to Plan 06), document the breakage + resolving plan in the phase-local deferred-items.md rather than expanding scope. Honors SCOPE BOUNDARY rule while preserving traceability.
- **Plan 01-04:** Defensive coercion at the LangGraph boundary — `args = raw_args if isinstance(raw_args, dict) else None` and `event.get("name") or ""` in `stream_agent`. LangGraph occasionally surfaces non-dict tool inputs (positional invocations) and unnamed events; without these coercions the new ToolStartEvent / ToolEndEvent Pydantic validation would raise mid-stream with no graceful error event (Plan 06's error handling isn't live yet).
- **Plan 01-05:** Used `except TimeoutError:` instead of plan-spec'd `except asyncio.TimeoutError:` — Python 3.11+ aliased `asyncio.TimeoutError` to the builtin `TimeoutError`, and ruff UP041 enforces the canonical builtin form. Pattern reusable for any future async exception handling under ruff UP rules.
- **Plan 01-05:** Sequencing Caveat Option A — `def load_profile(*, user_id=None, path=None)` keyword-only signature. Adding new params with leading `*` keeps existing positional/no-arg callers working without modification; new callers pass the new arg explicitly. Forward-compat shell pattern reusable for Phase 7 PROF-01 schema/source flips (load_profile body switches from `data/profile.json` to DB lookup keyed on user_id without touching call sites).
- **Plan 01-05:** `anyio.Event()` (NOT `asyncio.Event()`) for `app.state.shutdown_event` — sse-starlette's `shutdown_event` kwarg expects `anyio.Event` for asyncio/trio portability. Load-bearing choice for Plan 06's `EventSourceResponse(shutdown_event=app.state.shutdown_event, ping=...)` wiring.
- **Plan 01-05:** Documented anti-pattern in source comments (`# CRITICAL: do NOT add GZipMiddleware [D-18, Pitfall 6]`) — intentional anti-regression nudge for any future contributor adding middleware. Trade-off: literal-string `grep -rq GZipMiddleware src/` now matches the comment; runtime introspection `'GZipMiddleware' not in app.user_middleware` is the authoritative check (passes). Plan 06's CI grep should pivot to `grep -E "add_middleware\(\s*GZipMiddleware"` to ignore comments.
- **Plan 01-05:** Forward-compat function-body pattern for auth dependencies — `get_current_user_id()` returns a Python constant in v1; Phase 4 will rewrite the function body in-place to parse the Entra JWT `sub`/`oid` claim. No feature flag needed; every call site is already wired via `Depends(get_current_user_id)` so the rewrite is a one-function-body change. Decouples auth-wiring rollout (BACK-08, Phase 1) from auth-mechanism rollout (AUTH-06, Phase 4).

### Decisions (from PROJECT.md Key Decisions — carried forward for quick reference)

- Azure free tier over AWS: Berlin market is Azure-heavy; free tier covers year 1; direct interview talking point.
- Vite + React SPA + SWA (not Next.js): cleanest frontend/backend separation; matches educational goal.
- Entra External ID (not B2C, not workforce): same effort as passphrase login, real Azure skill, zero-rewrite to multi-user.
- `user_id` / `career_id` columns from day 1: ~10% migration cost now, saves painful refactor later.
- `IngestionSource` Protocol with one v1 implementation: decouples source from storage for future scrapers.
- One `PROMPT_VERSION` bump covers both `SkillCategory` enum and structured `Location`: amortize re-extraction cost.
- PDF/DOCX resume upload with show-and-confirm UX: reuses Instructor pattern; "inspectable AI" portfolio angle.
- RAGAS + CI gate: minimum viable MLOps loop.
- Terraform workspaces (dev + prod) from day 1.
- Linear-style dense aesthetic.

### Research-informed decisions (from research/SUMMARY.md)

- Use Entra External ID (CIAM tenant, `*.ciamlogin.com` authority), NOT Azure AD B2C (end-of-sale May 2025), NOT workforce tenant.
- RAGAS 0.4.3 (not 0.2) — bump is a breaking upgrade, must land as first Phase 8 action before harness code.
- GHCR (not ACR Basic) saves ~€60/yr, free egress from GitHub Actions.
- Reject PyMuPDF (AGPL, viral license risk) — use `pypdf` (BSD-3-Clause) + `python-docx` (MIT).
- `fetch` + `ReadableStream` for authenticated SSE (NOT EventSource — cannot attach Bearer headers; query-param tokens leak to logs).
- Tool-call chips (`tool_start` / `tool_end`) are the #1 portfolio signal — every competitor hides agent scaffolding.

### Todos

- (none)

### Blockers

- (none)

### Open Questions (from research, to resolve during planning)

- ~~Phase 1: Should `terminationGracePeriodSeconds=120` live in the Terraform Container App resource or in ACA YAML config?~~ → Resolved 2026-04-24 in Phase 1 CONTEXT.md (D-17): app-level SSE drain in Phase 1; Terraform `terminationGracePeriodSeconds=120` assigned to Phase 3 planner as belt-and-suspenders.
- Phase 2: Does the `PROMPT_VERSION` bump require invalidating existing embeddings, or only re-extracting text fields?
- Phase 3: Which Terraform resource type creates an Entra External ID tenant? Document manual bootstrap if none exists in `azuread ~> 3.x`.
- Phase 3: Is the SWA deployment token the only non-OIDC secret? Confirm at planning time.
- Phase 4: Should the Vite dev proxy point to local Docker Compose API or to the dev ACA deployment?
- Phase 6: Is `event: heartbeat` silently consumed, or should it drive a visible liveness indicator on the assistant bubble?
- Phase 7: Should source-line evidence be attempted in v1 or deferred to v1.x? FEATURES.md marks it P2.
- Phase 8: Eval cost per PR is ~€0.02 (~240 GPT-4o-mini calls). At what PR frequency does this become material?

## Session Continuity

### Last session summary

- 2026-04-23: Roadmap initialized. 8 phases mapped across 67 v1 requirements. Full coverage.
- 2026-04-24: Phase 1 context gathered (`.planning/phases/01-backend-prep/01-CONTEXT.md`). 4 gray areas discussed → 17 decisions captured (all Recommended). Locks: Alembic autogen+stamp baseline; dedicated `users` table + hardcoded `SEEDED_USER_ID`; typed `heartbeat` + `error` SSE events; app-level shutdown draining in Phase 1; async `IngestionSource` Protocol with thin sync bridge.
- 2026-04-27: Plan 01-01 executed (Wave 0 foundation). 2 atomic commits (246caad feat + 64345d0 test). Added alembic 1.18.4 + asgi-lifespan 2.1.0 deps; added 4 Settings fields (allowed_origins, seeded_user_id, agent_timeout_seconds, heartbeat_interval_seconds) with NoDecode CSV validator; added 6 Wave 0 scaffolding test files + 2 conftest fixtures. 82 tests pass / 18 skip / 0 fail. Plans 02-06 unblocked. Stopped at: Completed 01-01-PLAN.md (alembic + asgi-lifespan deps + 4 Settings fields + 6 Wave 0 test files); Plans 02-06 unblocked.
- 2026-04-27: Plan 01-02 executed (Alembic adoption). 2 atomic commits (55212c5 feat models/engine + 56307f4 feat alembic dir). Created alembic.ini + alembic/env.py + 3 migration files (0001 baseline, 0002 users + user_profile + seed, 0003 career_id); added UserDB + UserProfileDB ORM with NO default on user_id (D-12 invariant); added career_id column on JobPostingDB; rewrote init_db() to wrap alembic.command.upgrade(cfg, "head"); updated async_engine pool params (D-29). Stamped Adrian's dev DB at 0001 via direct INSERT (alembic ConfigParser doesn't handle % in URL-encoded password) then upgraded to 0003 — 108 postings preserved, career_id backfilled, seed user inserted. tests/test_alembic.py + tests/test_cli.py both ACTIVE and PASSING. Full suite: 83 passed, 17 skipped, 0 failed. Stopped at: Completed 01-02-PLAN.md.
- 2026-04-27: Plan 01-03 executed (IngestionSource Protocol). 2 atomic commits (9408e14 feat Protocol/RawPosting/MarkdownFileSource/IngestResult + 24afe5e feat ingest_from_source async consumer rewrap sync ingest_file). tests/test_ingestion.py ACTIVE.
- 2026-04-27: Plan 01-04 executed (SSE Pydantic event contract). 2 atomic commits (6ba420d feat api/sse.py + AgentEvent + to_sse + test scaffold guard widen + 35f2bbe feat stream.py rewire + test_agent + cli.py consumer fix). Created src/job_rag/api/sse.py with 6 Pydantic v2 BaseModel event classes + AgentEvent discriminated union via `Annotated[X | Y | ..., Field(discriminator="type")]` + `to_sse(event)` helper. Rewired src/job_rag/agent/stream.py to yield typed AgentEvent instances (return type `AsyncIterator[AgentEvent]`); 4 dict yields → Pydantic instances; defensive `isinstance(args, dict) else None` + `event.get("name") or ""` coercions for LangGraph edge cases. Updated tests/test_agent.py::TestStreamAgent (attribute access on Pydantic) and tests/test_sse_contract.py::TestOpenAPISchema (widened skip-guard for Plan 06 intermediate state). Auto-fixed src/job_rag/cli.py `agent --stream` consumer (Rule 1 — broke at runtime; not in plan but discovered via pyright full-tree scan). Wire-shape byte-identity confirmed via before/after smoke (5/5 events). routes.py:143 indexing deferred to Plan 06 (deferred-items.md tracks). Full suite: 97 passed, 5 skipped, 0 failed. Stopped at: Completed 01-04-PLAN.md.
- 2026-04-27: Plan 01-05 executed (FastAPI lifespan + CORS + get_current_user_id + asyncio.to_thread + load_profile user_id kwarg). 2 atomic commits (e968969 feat lifespan/CORS/auth + ab0657e feat asyncio.to_thread + load_profile). Rewrote src/job_rag/api/app.py: lifespan preloads `_get_reranker()` once on startup (BACK-03 closes 2-3s cold-load), creates `app.state.shutdown_event = anyio.Event()` and `app.state.active_streams = set()` (D-17), shutdown sets event then drains via `asyncio.wait_for(asyncio.gather(*active_streams), 30.0)` then disposes async DB engine; bumped version 0.2.0 → 0.3.0. CORSMiddleware wired with `allow_origins=settings.allowed_origins` (env-var driven, NEVER `*`), `allow_credentials=True`, GET/POST/OPTIONS, Authorization+Content-Type headers (BACK-01, T-05-01); explicit anti-regression comment forbids GZipMiddleware (D-18 / Pitfall 6). Appended `get_current_user_id() -> uuid.UUID` async dep to src/job_rag/api/auth.py returning `settings.seeded_user_id` directly (BACK-08, T-05-02 — body parses no input; Phase 4 rewrites body for Entra JWT per D-10). Wrapped `rerank()` callsite in src/job_rag/services/retrieval.py::rag_query as `await asyncio.to_thread(rerank, ...)` (BACK-04, T-05-03 — heartbeats keep firing); same wrap in src/job_rag/mcp_server/tools.py::search_postings. Evolved src/job_rag/services/matching.py::load_profile signature to `def load_profile(*, user_id: UUID | None = None, path: str | None = None)` keyword-only per Sequencing Caveat Option A — existing no-arg callers (api/routes.py /match + /gaps) keep working unchanged; mcp_server/tools.py callers now explicitly pass `user_id=settings.seeded_user_id` per D-08. Auto-fixed `except asyncio.TimeoutError` → `except TimeoutError` (Rule 1 — ruff UP041 enforces builtin alias for Python 3.11+). tests/test_lifespan.py reranker_preloaded + shutdown_event_initialized + tests/test_auth.py get_current_user_id all ACTIVE and PASSING. Full suite: 100 passed, 2 skipped, 0 failed (up from 97/5). routes.py:143 still deferred to Plan 06 (6 pyright errors, pre-existing from Plan 04 — NOT introduced by Plan 05). Stopped at: Completed 01-05-PLAN.md (lifespan + CORS + get_current_user_id + asyncio.to_thread + load_profile user_id kwarg). Plan 06 unblocked — only remaining Phase 1 plan.

### Next session

- `/gsd-discuss-phase 2` — gather Phase 2 (Corpus Cleanup) context: CORP-01..CORP-04 cover PROMPT_VERSION bump + SkillCategory enum + structured Location + full re-extraction. Or `/gsd-discuss-phase 3` for Infrastructure & CI/CD (DEPL-01..DEPL-12). Phases 2 and 3 are parallel-eligible per ROADMAP — pick whichever blocks downstream work first.
- Target plans per phase (standard granularity): 3-5.

---
*State initialized: 2026-04-23 after roadmap creation*
*Phase 1 context captured: 2026-04-24*
