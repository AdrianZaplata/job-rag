# Phase 2: Corpus Cleanup - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 ships a re-extracted 108-posting corpus when:

1. `JobRequirement` has both `skill_type` (renamed from existing 8-value `SkillCategory`) and a new `skill_category` (hard / soft / domain) field — the dashboard's filter axis.
2. `JobPosting` has an embedded `Location` Pydantic submodel (`country` ISO-3166 alpha-2 nullable, `city` nullable, `region` nullable) replacing the free-text `location: str` field.
3. The extraction prompt is tightened — a `REJECTED_SOFT_SKILLS` constant in `prompt.py` is interpolated into `SYSTEM_PROMPT` to make the LLM never extract universal LinkedIn fluff (communication, teamwork, problem-solving, etc.). Genuine soft signals (leadership, mentoring) still extracted and tagged.
4. `PROMPT_VERSION` bumped to `"2.0"` (major bump — schema-changing).
5. A new `job-rag reextract` CLI subcommand exists, idempotent (selects rows where `prompt_version != PROMPT_VERSION`), preserves embeddings, with `--all`, `--posting-id`, `--dry-run` flags. Per-posting commit on success, log+continue on failure.
6. Drift detection wired: `job-rag list --stats` prints `prompt_version` distribution; FastAPI lifespan startup logs a structured warning if any row has stale `prompt_version`.
7. The 108 existing postings are re-extracted against `PROMPT_VERSION = "2.0"`; the four roadmap success-criteria SQL sanity checks all pass.

Out of scope here (later phases): Azure infra (Phase 3), Entra/MSAL/JWT validation (Phase 4), Dashboard widgets that consume this data (Phase 5), Chat surface (Phase 6), Resume upload + profile CRUD (Phase 7), RAGAS + observability + docs (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### A. SkillCategory naming collision — rename existing, add new

- **D-01:** Rename existing `SkillCategory` enum (current 8 values: language, framework, cloud, database, concept, tool, soft_skill, domain) → `SkillType`. Field name on `JobRequirement` and DB column: `skill_type`. The existing tech-taxonomy information is preserved in full.
- **D-02:** Add new `SkillCategory` enum with three values: `HARD = "hard"`, `SOFT = "soft"`, `DOMAIN = "domain"`. Lives in `src/job_rag/models.py` alongside the renamed `SkillType`. New field on `JobRequirement`: `skill_category: SkillCategory`.
- **D-03:** `JobRequirement` has BOTH fields populated. `skill_type` is LLM-extracted (existing prompt logic preserved with `language → Python, framework → LangChain, ...`). `skill_category` is **deterministically derived in Python** from `skill_type`:
  - `language, framework, cloud, database, concept, tool` → `hard`
  - `soft_skill` → `soft`
  - `domain` → `domain`
  This avoids LLM tagging ambiguity, saves output tokens, and keeps the new dimension predictable. The mapping helper lives in `models.py` as `derive_skill_category(skill_type: SkillType) -> SkillCategory`.
- **D-04:** Migration `0004_corpus_cleanup.py` does (in order):
  1. `op.alter_column('job_requirements', 'category', new_column_name='skill_type')` — rename existing column.
  2. `op.add_column('job_requirements', Column('skill_category', String(20), nullable=False))` — note `nullable=False`; the migration data-step backfills using `derive_skill_category` SQL CASE before the constraint applies.
  3. Drop `ix_job_requirements_category`; create `ix_job_requirements_skill_type` and `ix_job_requirements_skill_category`.
- **D-05:** Existing call sites that read `JobRequirement.category` or `JobRequirementDB.category` (notably `services/matching.py`, `services/retrieval.py`, `mcp_server/tools.py`, agent tool layer) update to `skill_type`. The planner sweeps these in a dedicated plan.

### B. Location schema — embedded submodel, remote_policy unchanged

- **D-06:** Add `Location` Pydantic submodel in `src/job_rag/models.py`:
  ```python
  class Location(BaseModel):
      country: str | None = Field(default=None, description="ISO-3166 alpha-2 code")
      city: str | None = Field(default=None)
      region: str | None = Field(default=None)
  ```
  All three fields nullable.
- **D-07:** Replace `JobPosting.location: str` with `JobPosting.location: Location`. The free-text field is gone — every posting carries structured fields after re-extraction.
- **D-08:** ISO-3166 **alpha-2** for `country` (DE, PL, US, GB, ...). Matches Phase 5 dashboard URL convention (`?country=DE`); standard for locale codes.
- **D-09:** Non-country geographies use `country=null` + `region` populated. Concrete mapping examples:
  - `"Berlin, Germany"` → `{country: "DE", city: "Berlin", region: null}`
  - `"Munich, Bavaria, Germany"` → `{country: "DE", city: "Munich", region: "Bavaria"}`
  - `"Remote (EU)"` → `{country: null, city: null, region: "EU"}`
  - `"Worldwide"` / `"Global"` → `{country: null, city: null, region: "Worldwide"}`
  Phase 5's filter SQL handles `country=EU` dropdown via `WHERE country IN (<EU country list>) OR region='EU'`.
- **D-10:** **Deviation from CORP-03 spec**: the requirement text says `Location` includes `remote_allowed boolean`, but the existing `JobPosting.remote_policy: RemotePolicy` enum (REMOTE / HYBRID / ONSITE / UNKNOWN) is strictly richer than a boolean. **Keep `remote_policy` as a top-level field on `JobPosting`**; do **not** add `remote_allowed` to `Location`. Document this deviation in PROJECT.md's Key Decisions table when Phase 2 closes.
- **D-11:** DB representation on `job_postings` uses **flat columns with `location_` prefix**: `location_country: str | None (String(2))`, `location_city: str | None (String(255))`, `location_region: str | None (String(100))`. The existing `location: String(255)` column is dropped in the same migration. Pydantic ↔ ORM mapping is straightforward (no PostgreSQL composite type complexity).

### C. Re-extraction as a reusable CLI subcommand

- **D-12:** New CLI subcommand `job-rag reextract` in `src/job_rag/cli.py`. First-class, alongside `ingest`, `embed`, `serve`, `agent`, `mcp`, `reset`. Body delegates to an async service function `reextract_stale(*, all=False, posting_id=None, dry_run=False) -> ReextractReport` for testability.
- **D-13:** Service function lives in `src/job_rag/services/extraction.py` (new file) — keeps `services/ingestion.py` focused on the ingest path. `reextract_stale` operates on existing DB rows; it does NOT use the `IngestionSource` Protocol (which is for ingesting net-new content from sources).
- **D-14:** Default selection: `WHERE prompt_version != PROMPT_VERSION`. Idempotent — re-running after a partial failure picks up only the unchanged rows. Override flags:
  - `--all` — force re-extract every row regardless of `prompt_version` (escape hatch for prompt edits without version bump).
  - `--posting-id <uuid>` — single-posting debug.
  - `--dry-run` — count + log what would be re-extracted, no UPDATE.
- **D-15:** **Embeddings preserved** — re-extraction touches only structured fields (`title`, `company`, `location_country/city/region`, `salary_*`, `seniority`, `employment_type`, `responsibilities`, `benefits`, `prompt_version` on `job_postings`; rebuilds `job_requirements` rows). Does NOT touch `raw_text`, `job_postings.embedding`, `job_chunks.content`, `job_chunks.embedding`. Resolves STATE.md open question: "Phase 2: Does the PROMPT_VERSION bump require invalidating existing embeddings?" — **No.** Saves ~€0.05 + ~5min per run.
- **D-16:** Per-posting commit on success; per-posting rollback + structured log + continue on extraction failure. Final report counts succeeded / failed / skipped. Permanent failures (validation errors after 3 tenacity retries) do not abort the loop.
- **D-17:** Drift detection has two surfaces:
  - `job-rag list --stats` prints prompt_version distribution (e.g., `prompt_version=2.0: 102`, `prompt_version=1.1: 6 ⚠️ STALE`). This is also what CORP-04's success criteria check.
  - FastAPI lifespan startup runs `SELECT prompt_version, COUNT(*) FROM job_postings WHERE prompt_version != $1 GROUP BY prompt_version`; if rows returned, emits `log.warning("prompt_version_drift", stale_count=N, current=PROMPT_VERSION)`.

### D. Soft-skill rejection — hybrid (reject fluff, tag genuine signals)

- **D-18:** Add `REJECTED_SOFT_SKILLS: tuple[str, ...]` constant in `src/job_rag/extraction/prompt.py`. **Conservative list** (~22 terms) covering universal LinkedIn fluff:
  ```
  communication, teamwork, problem-solving, problem solving,
  analytical thinking, critical thinking, time management,
  work ethic, ownership mindset, ownership,
  attention to detail, detail-oriented,
  self-motivated, self-starter,
  customer focus, customer obsession,
  passion, drive, attitude, mindset,
  adaptability, flexibility
  ```
  Final wording is Claude's Discretion; the principle is "terms that appear on every LinkedIn ad regardless of role."
- **D-19:** `SYSTEM_PROMPT` becomes an f-string in `prompt.py` that interpolates `', '.join(REJECTED_SOFT_SKILLS)` into a "REJECTION RULES — NEVER extract these terms" section. Single source of truth — adding/removing a term is a one-line tuple edit + `PROMPT_VERSION` bump + `job-rag reextract`.
- **D-20:** Borderline policy — keep extracting these as `skill_type=soft_skill` (they're genuine senior-role differentiators, not fluff): `leadership`, `mentoring`, `stakeholder management`, `cross-functional collaboration`, `team leadership`. They derive to `skill_category=soft` via D-03. Phase 5 dashboard hides `soft` by default per DASH-01 with a "show soft skills" toggle (Phase 5's call to expose).
- **D-21:** Spoken languages (English, German, Polish, French, etc.) keep `skill_type=language` (existing prompt behavior). They derive to `skill_category=hard` per D-03. **Defensible because** spoken-language proficiency is a binary-checkable concrete requirement (German fluency is a real Berlin-postings filter for Adrian). The conceptual mismatch — `skill_type=language` originally meant programming languages — is acknowledged and deferred to a possible future `SkillType.NATURAL_LANGUAGE` split (see Deferred).
- **D-22:** `PROMPT_VERSION = "2.0"` (major bump from 1.1). Justified by structural changes: new `skill_category` field, structured `Location` replacing free-text `location`, `REJECTED_SOFT_SKILLS` enforcement. CORP-04's success criteria require the version-string change to be visible in `job-rag list --stats` output.

### Claude's Discretion

- Exact `Location` DB column lengths (`String(2)` for country alpha-2, `String(255)` for city, `String(100)` for region — pick reasonable defaults).
- Whether to add `ix_job_postings_location_country` index in migration 0004 — Phase 5 will filter by country heavily, but at 108 rows the planner can defer until Phase 3/5 needs it. Recommended: add it; index cost is trivial.
- Whether `reextract_stale` lives in a new `services/extraction.py` (D-13 default) or extends `services/ingestion.py`. New file preferred for layer-clarity (re-extraction is not ingestion); deferring to planner.
- Whether `--reembed` flag is exposed in v1 — defer until raw_text-affecting change actually arrives.
- Backup-before-reextract auto step (`pg_dump` integration). Safe default: document a manual pg_dump step in the plan; do NOT bake it into the CLI command (friction). Adrian's dev DB already has Phase 1 evidence that data preservation works through migrations.
- Specific prompt examples added to `SYSTEM_PROMPT` for Location structure (e.g., the four mapping examples in D-09). Wording is Claude's call as long as the structured-output behavior matches the deterministic mapping.
- Final values in `REJECTED_SOFT_SKILLS` — D-18 gives a conservative starting list; Claude can add/remove terms based on a quick survey of what shows up in the existing 108 postings' raw_text.
- Whether to preload PROMPT_VERSION drift count into `/health` endpoint response (vs lifespan-only log per D-17). Either is fine; lifespan log is the minimum.
- Validation strategy — the 4 roadmap SC give SQL-based checks. Whether to add a Python-side spot-check on N=5 postings (visual diff) is Claude's call.

### Folded Todos

None — STATE.md shows no pending todos relevant to Phase 2. CORP-01..CORP-04 from REQUIREMENTS.md are the authoritative scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing Phase 2.**

### Phase scope and requirements
- `.planning/REQUIREMENTS.md` §CORP-01 through §CORP-04 — the 4 v1 requirements Phase 2 owns
- `.planning/ROADMAP.md` §Phase 2 (Corpus Cleanup) — goal + 4 success criteria with concrete SQL checks
- `.planning/PROJECT.md` §Active §"Skill and location cleanup (one-time re-extraction)" — original capability list and motivation
- `.planning/PROJECT.md` §Key Decisions row "Re-extraction with structured Location + SkillCategory" — confirms one-bump-amortizes-both strategy

### Prior phase decisions (carried forward — do NOT re-litigate)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-01..D-05 — Alembic adoption: migration 0004 follows the established baseline → autogenerate → numbered file pattern with NullPool
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-13 — `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` is on `job_postings`; Phase 2 must preserve this column unchanged
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-20..D-24 — `IngestionSource` Protocol + `RawPosting` + `MarkdownFileSource` + `ingest_from_source` async consumer + `ingest_file` sync wrapper. Phase 2 reextract operates on DB rows directly; Protocol unchanged.
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-29 — async pool config (3+2, pre-ping, recycle 300s); reextract loop respects this — per-posting commit (D-16) avoids long-held connections.

### Pitfalls research (relevant to Phase 2)
- `.planning/research/PITFALLS.md` §Pitfall 8 — B1ms Postgres connection exhaustion. Reextract loop must commit per-posting (D-16) and not hold an outer transaction across all 108 LLM round-trips.
- `.planning/research/PITFALLS.md` §Pitfall 9 — pgvector extension already created in 0001 baseline. Migration 0004 does not touch the extension.

### Codebase audit (what exists, what gets renamed)
- `.planning/codebase/CONVENTIONS.md` §Naming — `StrEnum` for fixed sets (used by new `SkillCategory(hard/soft/domain)` and renamed `SkillType`); snake_case fields; type hints required.
- `.planning/codebase/ARCHITECTURE.md` §Layers — Ingestion → Retrieval+Matching → Intelligence layering preserved. Reextract sits inside the Ingestion layer (operates on stored postings), with no new layer introduced.
- `.planning/codebase/CONCERNS.md` §"Async/sync session dualism in ingest endpoint" — flagged in Phase 1 as deferred. Phase 2 does NOT close it; reextract is async-only by design (D-12), `ingest_file` retains its sync wrapper. Carried into Phase 2 deferred.

### Current backend state (files Phase 2 will touch)
- `src/job_rag/models.py` — rename `SkillCategory` → `SkillType`; add new `SkillCategory(hard/soft/domain)` enum; add `Location` submodel; change `JobPosting.location: str` → `JobPosting.location: Location`; add `derive_skill_category(skill_type) -> SkillCategory` helper; add `skill_category: SkillCategory` field to `JobRequirement`.
- `src/job_rag/extraction/prompt.py` — bump `PROMPT_VERSION` to `"2.0"`; add `REJECTED_SOFT_SKILLS` tuple; rewrite `SYSTEM_PROMPT` as an f-string interpolating the rejection list; extend with structured Location output instructions (4 mapping examples per D-09); preserve existing decomposition rules.
- `src/job_rag/db/models.py` — `JobRequirementDB.category` → `skill_type`; add `skill_category: Mapped[str] = mapped_column(String(20), nullable=False)`; on `JobPostingDB` drop `location: Mapped[str]`; add `location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)`, `location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)`, `location_region: Mapped[str | None] = mapped_column(String(100), nullable=True)`; preserve all other fields including `career_id`, `prompt_version`, `embedding`.
- `alembic/versions/0004_corpus_cleanup.py` — new migration: rename `category` → `skill_type`, add `skill_category`, swap indexes (D-04); drop `location` column, add `location_country/city/region`; data-backfill step for `skill_category` using SQL CASE on `skill_type`. Existing rows' `location_*` columns left null pending re-extraction (which fills them).
- `src/job_rag/cli.py` — new `reextract(all, posting_id, dry_run)` subcommand; extend `list --stats` to print prompt_version distribution per CORP-04 SC.
- `src/job_rag/services/extraction.py` (new file) — `reextract_stale(*, all=False, posting_id=None, dry_run=False) -> ReextractReport` async service function. Reuses `extract_posting` from `extraction/extractor.py` directly; UPDATEs structured fields and rebuilds `JobRequirementDB` rows per posting; per-posting commit per D-16.
- `src/job_rag/services/ingestion.py` — update `_store_posting` and `_store_posting_async` to write the new schema (skill_type, skill_category, location_country/city/region). Existing dedup-by-content_hash unchanged.
- `src/job_rag/services/matching.py` — update `_skill_matches` and any reads of `JobRequirementDB.category` to `skill_type`. Re-validate alias-group matching against the renamed enum values (no value changes, just attribute rename).
- `src/job_rag/services/retrieval.py` — update any reads of `JobRequirementDB.category` to `skill_type`. Cosine-distance retrieval logic unaffected.
- `src/job_rag/mcp_server/tools.py` — update tool serialization to emit both `skill_type` and `skill_category`. Existing JSON shape changes — bump tool schema version if there's a downstream MCP consumer (only Adrian via Claude Code in v1).
- `src/job_rag/api/app.py` — extend FastAPI lifespan startup to query prompt_version drift and emit a structured warning per D-17.
- `tests/test_models.py` — Pydantic round-trip tests for `JobPosting` with `Location` submodel; for `JobRequirement` with both `skill_type` and `skill_category`; for `derive_skill_category` (8 inputs, 3 outputs).
- `tests/test_extraction.py` — update existing extraction tests for new prompt outputs (rejection rules, Location structure).
- `tests/test_reextract.py` (new) — CLI smoke tests for `job-rag reextract`, `--dry-run`, `--posting-id`, `--all`; partial-failure handling per D-16; idempotency check (run twice, second is a no-op).
- `tests/test_alembic.py` — extend with 0004 upgrade/downgrade smoke; verify rename + new columns + index swap.
- `tests/conftest.py` — fixtures may need updating for the new schema (skill_type, location_country/city/region).

### Stack baselines (no new deps)
- `src/job_rag/extraction/extractor.py` — Instructor 1.x + GPT-4o-mini already in place; reextract reuses `extract_posting` directly.
- `pyproject.toml` — no new dependencies for Phase 2. (Future Phase 7 adds `pypdf` + `python-docx`; not Phase 2.)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`extract_posting(raw_text) -> tuple[JobPosting, dict]`** (`src/job_rag/extraction/extractor.py`) — already retried via tenacity, already records `prompt_version` in usage_info. Reextract reuses this verbatim; only the `JobPosting` Pydantic schema underneath changes.
- **`@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))`** decorator — handles transient LLM failures inside `extract_posting`. Reextract's per-posting log+continue (D-16) handles permanent failures on top.
- **`_sanitize_delimiters(text)`** (`extraction/extractor.py`) — strips `<job_posting>` / `</job_posting>` tags from raw_text. Already in place; reextract benefits without code change.
- **structlog `get_logger(__name__)`** pattern — used in every service module. Phase 2's reextract emits `reextract_started`, `reextract_posting_complete`, `reextract_complete`, `reextract_failed` events for Langfuse-friendly observability.
- **Phase 1's Alembic infrastructure** (D-01..D-05) — env.py with pgvector type registration, NullPool engine, `alembic.command.upgrade(cfg, "head")` wrapper in `init_db()`. Migration 0004 plugs into this unchanged.
- **`UserDB`, `UserProfileDB`, `career_id`** (Phase 1 D-06..D-13) — preserved. Phase 2 migration 0004 must not touch users-related tables. The `users` row for Adrian's `SEEDED_USER_ID` survives the corpus-only schema changes.
- **`job-rag reset` command** — unchanged, still nuclear option (delete-all). `job-rag reextract` is the surgical complement; both coexist for different scenarios.

### Established Patterns
- **`StrEnum` convention** — `SkillCategory(StrEnum)`, `RemotePolicy(StrEnum)`, `Seniority(StrEnum)`, `SalaryPeriod(StrEnum)` already in `models.py`. New `SkillType` (renamed) and new `SkillCategory(hard/soft/domain)` follow the same pattern.
- **SQLAlchemy 2.x `Mapped[]` syntax** — `mapped_column(String(20), nullable=False)`, `Mapped[str]`, `Mapped[str | None]`. New columns in 0004 follow this exactly.
- **Async query pattern** — `from sqlalchemy import select` + `await session.execute(stmt)` + `result.scalar_one_or_none()`. Reextract loop uses this.
- **Per-statement commit in batch operations** (`services/ingestion.py` `ingest_from_source`) — already commits per-iteration so partial failures don't roll back earlier successes. Reextract follows the same pattern.
- **Defensive coercion at LLM boundary** (Phase 1 Plan 04 D-04 pattern) — for new optional fields like `location.city` and `location.region` that may come back as null/missing from the LLM, Pydantic's `default=None` handles it. No special LangGraph-style coercion needed.
- **Prompt versioning + corpus invalidation** — already documented in CONVENTIONS.md and PROJECT.md as a project convention. Phase 2 just adds the surgical `job-rag reextract` path on top of the existing nuclear `job-rag reset` path.

### Integration Points
- **`job-rag ingest data/postings/`** — unchanged. Continues to use current `PROMPT_VERSION` on new files. Existing `content_hash` dedup means re-running ingest does NOT re-extract existing rows (that's reextract's job).
- **`job-rag list --stats`** — extend to print `prompt_version` distribution per CORP-04 SC. Hooks drift detection.
- **`job-rag reset`** — unchanged. Different use case (full reset on dev clean-slate).
- **FastAPI lifespan startup** (`api/app.py`, Phase 1 D-17) — already has the `@asynccontextmanager` lifespan with reranker preload + shutdown drain. Phase 2 adds a one-shot prompt_version drift check inside the same startup hook.
- **Phase 5 (Dashboard) — downstream consumer** — `DASH-01` filters by `skill_category=hard` (default) with show-soft toggle; `DASH-02` salary band query; `DASH-04` country dropdown matches `location_country` (or `location_region` for EU/Worldwide). Phase 2 must produce the schema Phase 5 expects.
- **`/match`, `/gaps`, `/agent`, `/agent/stream`** — Phase 1 already wired `Depends(get_current_user_id)`; Phase 2 changes the JobRequirement schema, which affects these endpoints' response shapes (now include `skill_type` AND `skill_category`). MCP tool schemas need a refresh — Adrian (single-user) is the only consumer in v1.
- **Langfuse tracing** — `extract_posting` is already traced via `get_openai_client()` returning the Langfuse-wrapped client. Reextract calls inherit traces; the loop's structured log events provide additional spans.
- **Docker Compose / docker-entrypoint** — calls `job-rag init-db` on startup which wraps `alembic upgrade head` (Phase 1 D-04). Migration 0004 ships via the same path. No docker-compose changes.
- **`.github/workflows/ci.yml`** — Phase 1 added postgres service + alembic upgrade smoke + grep guard for user_id DEFAULT. Phase 2 doesn't add new CI surface; the existing alembic smoke catches 0004's issues.

</code_context>

<specifics>
## Specific Ideas

- Phase 1's CONTEXT.md noted Adrian "consistently selected the Recommended option across all 17 sub-decisions, signalling trust once tradeoffs were explicit." Phase 2 confirms this pattern unchanged across all 16 sub-decisions. Downstream agents should continue presenting recommendation + rationale + counterfactuals, not bare alternatives. Skip "you decide" placeholder options — give real choices.
- Adrian reframed Area 3 mid-discussion ("I'll be adding new postings over time, what's the best strategy?"), shifting Phase 2's re-extraction design from a one-shot script to a first-class CLI subcommand with idempotent semantics. This was captured both as a Phase 2 decision (D-12..D-17) and as a memory entry for future GSD discussions: `~/.claude/projects/.../memory/feedback_reusable_tools.md`. Future phases (especially anything cleanup / migration / refresh-shaped) should default to the same reusable-tool framing without needing to re-derive the principle.
- The conceptual mismatch between `skill_type=language` (originally programming languages) and spoken languages (English, German, Polish) is acknowledged and accepted for v1 (D-21). The deterministic `skill_category=hard` derivation is defensible because spoken-language requirements are concrete-checkable. If Phase 5's dashboard reveals a noticeable user-facing mismatch (e.g., "Top hard skills" lists "English" alongside "Python"), revisit with `SkillType.NATURAL_LANGUAGE`. Captured in Deferred.
- The CORP-03 spec literally says `Location` includes `remote_allowed boolean`. Phase 2 deliberately deviates (D-10) — `remote_policy: RemotePolicy` is strictly richer and already exists. Document this deviation in PROJECT.md's Key Decisions table at phase close so the project history reflects the considered choice, not silent drift.
- The `REJECTED_SOFT_SKILLS` tuple is single-source-of-truth in `prompt.py` (D-18, D-19) — the SYSTEM_PROMPT f-string interpolates the same tuple that any post-extraction validation would import. No two-list drift risk.

</specifics>

<deferred>
## Deferred Ideas

- **Full async-ingest pipeline refactor** (carried forward from Phase 1 deferred). Closing CONCERNS.md "Async/sync session dualism" for `/ingest` and the CLI is non-scope for Phase 2. The reextract path goes through async-only by design (D-12), but `ingest_file` retains its Phase 1 D-24 sync-wrapper. Candidate for v2 tech-debt phase.
- **`SkillType.NATURAL_LANGUAGE` distinct from `SkillType.LANGUAGE`** — splits programming languages from spoken languages so the deterministic mapping can route them differently (NATURAL_LANGUAGE → domain). Not needed for v1 because skill_category=hard is defensible for spoken-language proficiency. Resurface if Phase 5's dashboard surfaces the mismatch.
- **Country index** (`ix_job_postings_location_country`) — Phase 5's dashboard filters by country heavily. Migration 0004 may add it (recommended in Claude's Discretion); if planner defers for sample-size reasons (108 rows is below the threshold where indexes pay off), add later when corpus grows.
- **`pg_dump` integration into `job-rag reextract`** — auto-backup-before-run. Skipped in v1 to keep CLI command friction-free; manual `pg_dump` is a documented step in the Phase 2 plan SUMMARY. Revisit when corpus is ≥1000 postings or if a real reextract failure causes data loss.
- **Reject-list externalization** — `REJECTED_SOFT_SKILLS` lives in `prompt.py` for v1 (D-18). If Adrian iterates on the list weekly (signal: 5+ list edits per month), externalize to `data/extraction/reject-skills.json` so prompt edits don't trigger PROMPT_VERSION bumps for trivial term additions.
- **`--reembed` flag for `job-rag reextract`** — belt-and-suspenders for a future change to chunking logic. Skipped in v1 because raw_text → chunk → embedding pipeline is unchanged in Phase 2. Add when chunking logic actually changes.
- **PROMPT_VERSION drift health-check endpoint** — `/health` could report stale-row count. D-17 chooses lifespan-only logging for v1 (lighter touch). Add to `/health` if Phase 8 documentation harness or monitoring needs a programmatic surface.
- **Python-side spot-check tool** — visual diff of N=5 randomly-selected postings before/after re-extraction, to catch subtle prompt regressions. Beyond CORP-04's SQL sanity checks. Claude's Discretion on whether to fold into Phase 2 plan or defer to Phase 8.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 2` returned `todo_count: 0`.

</deferred>

---

*Phase: 02-corpus-cleanup*
*Context gathered: 2026-04-27*
