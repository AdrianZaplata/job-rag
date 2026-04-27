# Phase 2: Corpus Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 02-corpus-cleanup
**Areas discussed:** SkillCategory name collision, Location schema vs remote_policy, Re-extraction execution mechanics, Soft-skill noise rejection criteria

---

## Gray Area Selection

**Question:** Phase 2 (Corpus Cleanup) — which gray areas do you want to discuss?

| Option | Description | Selected |
|--------|-------------|----------|
| SkillCategory name collision | Existing SkillCategory enum collides with CORP-02's needed hard/soft/domain enum. | ✓ |
| Location schema vs remote_policy | CORP-03 adds remote_allowed bool but remote_policy enum already exists. ISO format. EU/Worldwide handling. | ✓ |
| Re-extraction execution mechanics | One-shot script vs CLI subcommand. Embedding handling. Backup. Failure modes. | ✓ |
| Soft-skill noise rejection criteria | What's on the reject list. Borderline cases (leadership, mentoring, spoken languages). | ✓ |

**User's choice:** All four areas selected.

---

## SkillCategory name collision

### Q1: How should the SkillCategory naming collision be resolved?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename existing + add new (Recommended) | Rename current 8-value enum to SkillType, add new SkillCategory(hard/soft/domain). Both columns on JobRequirement. Zero data loss. | ✓ |
| Replace existing with new | Drop the 8-value enum, replace with hard/soft/domain. Loses tech taxonomy. | |
| Keep existing, derive new at query time | No schema change to enum. Compute hard/soft/domain in queries. | |

**User's choice:** Rename existing + add new (Recommended).
**Notes:** Selected with preview showing dual-field JobRequirement Pydantic model.

### Q2: What should the existing 8-value enum be renamed to?

| Option | Description | Selected |
|--------|-------------|----------|
| SkillType (Recommended) | Short, clear; field name skill_type. | ✓ |
| SkillTaxonomy | More precise but longer. | |
| SkillFamily | Taxonomic flavor, less common in code. | |

**User's choice:** SkillType (Recommended).

### Q3: How should JobRequirement.skill_category (hard/soft/domain) be populated during extraction?

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic Python mapping (Recommended) | LLM tags skill_type only; Python derives skill_category. Predictable, saves tokens. | ✓ |
| LLM tags both fields directly | Prompt asks LLM to output both. More flexible, more tokens, drift risk. | |
| Hybrid: LLM tags, Python validates | Belt-and-suspenders. Overkill for v1. | |

**User's choice:** Deterministic Python mapping (Recommended).
**Notes:** Mapping helper `derive_skill_category(skill_type)` lives in models.py. soft_skill→soft, domain→domain, rest→hard.

### Q4: Should the JobRequirementDB.category column be renamed to match the new Pydantic field?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename column to skill_type (Recommended) | Pydantic, DB column, ORM attribute all match. Migration also adds skill_category column. Indexes swapped. | ✓ |
| Keep column name `category` | Less migration churn, but Pydantic-DB mismatch is a future-confusion risk. | |

**User's choice:** Rename column to skill_type (Recommended).
**Notes:** Selected with preview showing concrete Alembic alter_column + add_column + index swap.

---

## Location schema vs remote_policy

### Q1: How should the Location data be shaped on the Pydantic model?

| Option | Description | Selected |
|--------|-------------|----------|
| Embedded Location model (Recommended) | JobPosting.location: Location submodel. Cleaner namespacing for future fields. | ✓ |
| Flat columns on JobPosting | country/city/region as top-level fields. Simpler ORM, more JobPosting churn if location grows. | |

**User's choice:** Embedded Location model (Recommended).

### Q2: How should the new Location schema interact with the existing remote_policy enum?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep remote_policy, drop spec's remote_allowed (Recommended) | Location holds country/city/region only. remote_policy enum stays separate (richer). Documents deviation from CORP-03 spec. | ✓ |
| Add remote_allowed to Location, derive from remote_policy | Spec-literal but redundant. Drift risk. | |
| Move remote_policy INTO Location | Cleanest namespacing but breaks every existing call site. | |

**User's choice:** Keep remote_policy, drop spec's remote_allowed (Recommended).

### Q3: What ISO-3166 country code format should be used?

| Option | Description | Selected |
|--------|-------------|----------|
| alpha-2 (DE, PL, US) (Recommended) | Two-letter codes; matches Phase 5 dashboard URL convention; standard for locale codes. | ✓ |
| alpha-3 (DEU, POL, USA) | Three-letter; visually heavier; not what dashboard URLs use. | |
| ISO numeric (276, 616, 840) | Unreadable; atypical for web apps. | |

**User's choice:** alpha-2 (Recommended).

### Q4: How should non-country geographies (EU, Worldwide) be represented?

| Option | Description | Selected |
|--------|-------------|----------|
| country=null, region populated (Recommended) | EU → country=null, region='EU'. Worldwide → country=null, region='Worldwide'. | ✓ |
| Pseudo-codes in country (EU, WW) | Breaks ISO-3166 invariant; downstream silently misbehaves. | |
| Separate geo_scope enum | Explicit but adds a third dimension to filter logic. | |

**User's choice:** country=null, region populated (Recommended).
**Notes:** Selected with preview showing the four canonical mapping examples (Berlin, Munich, Remote(EU), Worldwide).

---

## Re-extraction execution mechanics

> **Reframe note:** Adrian's clarifying question ("I'll be adding new postings over time, what's the best strategy here?") shifted the framing from "one-time Phase 2 event" to "reusable tool for ongoing prompt iteration." The four questions were rewritten around the steady-state mental model. The reframe surfaced the design that matched Adrian's actual workflow.

### Q1: Where should the re-extraction logic live?

| Option | Description | Selected |
|--------|-------------|----------|
| job-rag reextract CLI subcommand (Recommended) | First-class CLI alongside ingest/embed/reset. Discoverable, testable. Body delegates to services/extraction.py. | ✓ |
| scripts/reextract.py standalone | Lives in scripts/. Less discoverable, harder to wire tests. | |
| Both (script wrapping CLI logic) | Three entry points to maintain. | |

**User's choice:** job-rag reextract CLI subcommand (Recommended).
**Notes:** Selected with preview showing the Typer command body and Adrian's three-step workflow.

### Q2: How does the tool select which postings to re-extract?

| Option | Description | Selected |
|--------|-------------|----------|
| Stale-only by default, --all override (Recommended) | Default: WHERE prompt_version != PROMPT_VERSION. Idempotent. --all + --posting-id overrides. | ✓ |
| Always all, no filter | Wastes LLM cost on every iteration. | |
| By date range | Useful for sliced backfills but rarely the right cut. | |

**User's choice:** Stale-only by default, --all override (Recommended).

### Q3: Should the tool touch embeddings on job_chunks?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave embeddings alone (Recommended) | raw_text→chunks→embeddings pipeline unchanged in Phase 2. Saves cost. Resolves STATE.md open question. | ✓ |
| Optional --reembed flag | Default leaves alone; flag regenerates for future chunking changes. | |
| Always regenerate embeddings | Belt-and-suspenders with no benefit when raw_text doesn't change. | |

**User's choice:** Leave embeddings alone (Recommended).
**Notes:** Selected with preview enumerating exactly which DB fields reextract touches vs preserves.

### Q4: How should the system surface prompt_version drift between runs?

| Option | Description | Selected |
|--------|-------------|----------|
| list --stats + startup log (Recommended) | CLI stats command shows distribution; FastAPI lifespan logs warning on stale rows. No silent drift. | ✓ |
| list --stats only, no startup log | Quieter; risk of forgetting after a bump. | |
| Hard fail on drift at startup | Forces fix-now discipline but blocks dev workflow during prompt iteration. | |

**User's choice:** list --stats + startup log (Recommended).
**Notes:** Selected with preview showing both CLI output and structured log call.

---

## Soft-skill noise rejection criteria

### Q1: What's the strategy for soft-skill noise?

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: reject pure fluff, tag genuine soft skills (Recommended) | Prompt rejects ~22 universal LinkedIn fluff terms; legitimate soft signals (leadership, mentoring) extracted and tagged. | ✓ |
| Hardcoded reject only — no soft skills at all | Cleanest dashboard; loses senior-role signals. Goes beyond CORP-01 spec. | |
| Tag-only (no rejection) | Rely on dashboard filter; ~30% corpus pollution risk. | |

**User's choice:** Hybrid (Recommended).
**Notes:** Selected with preview showing reject list + extract-but-tag list.

### Q2: What's the canonical reject list (LLM never extracts these)?

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative — universal fluff only (Recommended) | ~22 terms covering universal LinkedIn fluff. | ✓ |
| Aggressive — reject most soft skills | Drops genuine senior-role signals. | |
| Minimal — only the worst offenders | Lets too much through. | |

**User's choice:** Conservative (Recommended).
**Notes:** Selected with preview showing the concrete REJECTED_SOFT_SKILLS tuple.

### Q3: How should borderline soft-adjacent skills be handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as soft_skill, tag soft (Recommended) | Leadership/mentoring/stakeholder management → skill_type=soft_skill. Spoken languages → skill_type=language. | ✓ |
| Keep as soft_skill, reject spoken languages | Loses German-required signal for Berlin postings. | |
| Drop borderline cases too | Loses real signal at senior levels. | |

**User's choice:** Keep as soft_skill, tag soft (Recommended).
**Notes:** Selected with preview showing concrete decomposition examples. Caveat: the preview comment "(skill_category derives to 'domain')" was inconsistent with Q3 of Area 1 (deterministic mapping → hard for skill_type=language). Captured in CONTEXT.md D-21 as accepted (skill_category=hard for spoken languages is defensible) and as a Deferred item if Phase 5 reveals user-facing mismatch.

### Q4: Where does the reject list live and how is it maintained?

| Option | Description | Selected |
|--------|-------------|----------|
| Constant in prompt.py, referenced from SYSTEM_PROMPT (Recommended) | REJECTED_SOFT_SKILLS tuple, f-string interpolation. Single source of truth. | ✓ |
| Inline list embedded in prompt text | Less reusable for tests; harder to introspect. | |
| Separate JSON file (data/extraction/reject-skills.json) | Version-decoupled from prompt; drift risk. | |

**User's choice:** Constant in prompt.py (Recommended).
**Notes:** Selected with preview showing concrete f-string structure with PROMPT_VERSION = "2.0" bump.

---

## Claude's Discretion

Areas where the user explicitly accepted Claude's flexibility for the planner / executor:

- Exact `Location` DB column lengths (`String(2)` for country, `String(255)` for city, `String(100)` for region — pick reasonable defaults).
- Whether to add `ix_job_postings_location_country` index in migration 0004.
- Whether `reextract_stale` lives in a new `services/extraction.py` (default) or extends `services/ingestion.py`.
- Whether `--reembed` flag is exposed in v1 (deferred).
- Backup-before-reextract `pg_dump` integration (manual step in plan SUMMARY rather than baked into CLI).
- Specific prompt examples added for Location structure mapping.
- Final wording of `REJECTED_SOFT_SKILLS` terms.
- Whether to preload PROMPT_VERSION drift count into `/health` endpoint response (vs lifespan-only log).
- Validation strategy beyond CORP-04's SQL sanity checks — Python-side spot-check on N=5 postings is Claude's call.

---

## Deferred Ideas

Ideas mentioned during discussion that were noted for future phases:

- **Full async-ingest pipeline refactor** (carried forward from Phase 1 deferred).
- **`SkillType.NATURAL_LANGUAGE` distinct from `SkillType.LANGUAGE`** — for spoken-language separation if Phase 5 dashboard reveals mismatch.
- **Country index** (`ix_job_postings_location_country`) — may add now, otherwise Phase 5 timing.
- **`pg_dump` integration into `job-rag reextract`** — auto-backup-before-run; v1 keeps manual.
- **Reject-list externalization** to JSON config file — only if Adrian iterates weekly.
- **`--reembed` flag** — only if chunking logic changes.
- **PROMPT_VERSION drift health-check endpoint** — lifespan-only log in v1.
- **Python-side spot-check tool** — visual diff for prompt regression catching beyond SQL checks.
