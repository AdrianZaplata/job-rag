---
status: complete
phase: 02-corpus-cleanup
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md]
started: 2026-04-28T14:42:09Z
updated: 2026-04-28T16:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Boot FastAPI app fresh; lifespan startup completes without errors. A `prompt_version_drift` log emits with `current=2.0` and `stale_count=10` (or `prompt_version_check_clean` if 10 residuals were retried). `/health` returns 200.
result: pass
verified_by: claude
notes: |
  `_run_lifespan_check.py` produced clean lifespan_startup_begin → reranker_preloaded
  → `prompt_version_drift current=2.0 stale_by_version={'1.1': 10} stale_count=10`.
  Booted uvicorn separately and `GET /health` returned `{"status":"ok"}` HTTP 200.

### 2. CLI: `job-rag list --stats` prompt-version distribution
expected: Running `uv run job-rag list --stats` (with DATABASE_URL exported) prints `=== Prompt version distribution (current: 2.0) ===` then `prompt_version=2.0: 98` and `prompt_version=1.1: 10 STALE`, total 108, plus the remediation hint `Stale: 10 - run `job-rag reextract` to refresh.`
result: pass
verified_by: claude
notes: |
  Output matched expectation exactly: 2.0=98, 1.1=10 STALE, total 108,
  remediation footer present.

### 3. CLI: `job-rag list` default view shows Country column
expected: Running `uv run job-rag list` (no flags) prints a posting table with a `Country` column (e.g. `DE`, `PL`, `US`, `-`) instead of the old free-text `Location` column.
result: pass
verified_by: claude
notes: |
  Header reads `Company  Title  Country  Remote`. Values include `DE`, `PL`,
  and `-` (for the 10 stale rows whose location_country is still NULL).
  No old free-text `Location` column visible.

### 4. CLI: `job-rag reextract --dry-run` selects stale rows
expected: Running `uv run job-rag reextract --dry-run` reports `Selected: 10` (the 10 residual `prompt_version='1.1'` postings) and exits without mutating the DB. No LLM calls made.
result: pass
verified_by: claude
notes: |
  `reextract_started` event reports `selected=10 dry_run=True`.
  Final report: Selected=10, Succeeded=0, Failed=0, Skipped=10, $0.0000.

### 5. CLI: `job-rag reextract --all` confirmation guard
expected: Running `uv run job-rag reextract --all` (without `--yes`) shows a `typer.confirm` prompt asking to confirm refreshing all postings. Answering "n" aborts with non-zero exit; no DB mutation.
result: pass
verified_by: claude
notes: |
  Prompted: `Re-extract EVERY posting regardless of prompt_version?
  (~3-5 minutes, ~€0.20) [y/N]:`. Stdin "n" → `Aborted.`, exit code 1.
  No DB mutation occurred (abort fires before reextract loop).

### 6. DB schema: migration 0004 applied
expected: Inspecting the dev DB shows: `job_postings` has columns `location_country` (varchar(2)), `location_city`, `location_region` and no free-text `location` column; `job_requirements` has `skill_type` and `skill_category` columns; index `ix_job_postings_location_country` exists. Counts: 108 postings preserved, 1987+ requirements present.
result: pass
verified_by: claude
notes: |
  `\d job_postings` shows location_country varchar(2), location_city varchar(255),
  location_region varchar(100); no `location` column. Index
  `ix_job_postings_location_country` present. `\d job_requirements` shows
  skill_type + skill_category (both varchar(20), NOT NULL) plus matching indexes.
  Counts: 108 postings / 1987 requirements.

### 7. DB content: skill_category populated, no NULLs
expected: `SELECT skill_category, COUNT(*) FROM job_requirements GROUP BY skill_category` returns three buckets (`hard`, `soft`, `domain`) with `hard` dominant (~92%). `SELECT COUNT(*) FROM job_requirements WHERE skill_category IS NULL` returns 0.
result: pass
verified_by: claude
notes: |
  Three buckets: hard=1843 (92.8%), domain=77 (3.9%), soft=67 (3.4%).
  NULL count=0. Distribution matches plan 04 SUMMARY (1843/77/67) — Plan 03's
  earlier 1844/156/121 backfill was overwritten when 98 postings were
  reextracted under PROMPT_VERSION=2.0 with derive_skill_category() applied
  to LLM-emitted skill_type values.

### 8. MCP tool: nested location + structured requirements
expected: Calling MCP `search_postings` (e.g. via Claude Code MCP client or a direct tool invocation) returns posting dicts where `location` is a nested object `{country, city, region}` and `must_have`/`nice_to_have` are arrays of `{skill, skill_type, skill_category}` dicts — not the old flat strings.
result: pass
verified_by: claude
notes: |
  Invoked `_serialize_posting` directly on a Netguru posting. Output:
    "location": {"country": "PL", "city": "Poznań", "region": null}
    "must_have": [{"skill": "Python", "skill_type": "language", "skill_category": "hard"}, ...]
    "nice_to_have": [{"skill": "Azure ML", "skill_type": "cloud", "skill_category": "hard"}, ...]
  Shape matches Plan 03 SUMMARY contract exactly.
side_observation: |
  Salary fields on this posting are swapped: salary_min=27144 > salary_max=22620.
  Raw is `2,262 EUR net/month (B2B) or 1,885 EUR gross/month (Permanent)`; LLM
  annualized both but put net-B2B (higher) in min and gross-Permanent (lower)
  in max. Data-quality issue from extraction, not Phase 2 schema scope. Worth
  flagging for a future eval/extraction-quality plan.

### 9. Drift remediation surface visible from CLI
expected: After running `job-rag list --stats`, the 10 stale postings are clearly flagged with the `STALE` marker on the `prompt_version=1.1` line, and the footer prints the remediation command. (Sanity check that drift is observable, not silent.)
result: pass
verified_by: claude
notes: |
  Already verified under Test 2: `prompt_version=1.1: 10 STALE` line plus
  footer `Stale: 10 - run `job-rag reextract` to refresh.` This test is a
  redundant phrasing of Test 2 — passing it on the same evidence.

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
