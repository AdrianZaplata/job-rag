---
phase: 2
slug: corpus-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3+ (with `pytest-asyncio`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_models.py tests/test_extraction.py -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~30-60 seconds (full suite, excluding integration-marked) |

---

## Sampling Rate

- **After every task commit:** Run quick command above (focused on touched test file)
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite green + 4 SQL sanity checks (CORP-01..CORP-04) executed
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | CORP-02 | — | N/A | unit | `uv run pytest tests/test_models.py::TestSkillType -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | CORP-02 | — | N/A | unit | `uv run pytest tests/test_models.py::TestSkillCategoryDerivation -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | CORP-03 | — | N/A | unit | `uv run pytest tests/test_models.py::TestLocation -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | CORP-02, CORP-03 | T-DB-01 (migration data loss) | NOT NULL constraint enforced; backfill before constraint | unit | `uv run pytest tests/test_alembic.py::test_0004_upgrade_smoke -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | CORP-02, CORP-03 | — | Downgrade restores prior schema | unit | `uv run pytest tests/test_alembic.py::test_0004_downgrade_smoke -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | CORP-01 | T-PROMPT-01 (prompt injection via REJECTED_SOFT_SKILLS) | Tuple values not user-controlled; literal interpolation | unit | `uv run pytest tests/test_extraction.py::TestPromptStructure -x` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 1 | CORP-01 | — | N/A | unit | `uv run pytest tests/test_extraction.py::TestRejectionRulesUnit -x` | ✅ | ⬜ pending |
| 02-02-03 | 02 | 2 | CORP-01 | — | N/A | integration | `uv run pytest tests/test_extraction.py::TestRejectionRulesLive -x -m integration` | ✅ | ⬜ pending |
| 02-03-01 | 03 | 2 | CORP-01..04 | — | N/A | unit | `uv run pytest tests/test_reextract.py::TestReextractStaleDefault -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | CORP-01..04 | — | N/A | unit | `uv run pytest tests/test_reextract.py::TestReextractIdempotency -x` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 2 | CORP-01..04 | T-CLI-01 (--all without confirm) | `--all` requires `--yes` or interactive confirm | unit | `uv run pytest tests/test_reextract.py::TestReextractAllConfirm -x` | ❌ W0 | ⬜ pending |
| 02-03-04 | 03 | 2 | CORP-01..04 | — | N/A | unit | `uv run pytest tests/test_reextract.py::TestPartialFailureContinues -x` | ❌ W0 | ⬜ pending |
| 02-03-05 | 03 | 2 | CORP-04 | — | N/A | unit | `uv run pytest tests/test_cli.py::TestListStatsPromptVersion -x` | ❌ W0 | ⬜ pending |
| 02-03-06 | 03 | 2 | CORP-04 | — | N/A | unit | `uv run pytest tests/test_lifespan.py::TestPromptVersionDriftWarning -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | CORP-01..04 | — | Per-posting commit isolates failures | manual+sql | 4 SQL queries (see Manual-Only Verifications) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: Task IDs above are placeholders — final IDs assigned by gsd-planner. Mapping survives because each row is keyed by (Plan, Test Class).*

---

## Wave 0 Requirements

- [ ] `tests/test_models.py` — extend with `TestSkillType`, `TestSkillCategoryDerivation`, `TestLocation` classes (REQ CORP-02, CORP-03)
- [ ] `tests/test_extraction.py` — extend with `TestPromptStructure` + `TestRejectionRulesUnit` + `TestRejectionRulesLive` classes (REQ CORP-01)
- [ ] `tests/test_alembic.py` — extend with `test_0004_upgrade_smoke` + `test_0004_downgrade_smoke` (REQ CORP-02, CORP-03)
- [ ] `tests/test_reextract.py` — NEW file with `TestReextractStaleDefault`, `TestReextractIdempotency`, `TestReextractAllConfirm`, `TestPartialFailureContinues` classes (REQ CORP-01..04)
- [ ] `tests/test_cli.py` — extend with `TestListStatsPromptVersion` class (REQ CORP-04)
- [ ] `tests/test_lifespan.py` — NEW file with `TestPromptVersionDriftWarning` class (REQ CORP-04)
- [ ] `tests/conftest.py` — update fixtures for new schema (`skill_type`, `skill_category`, `location_country/city/region`)

*Framework already installed via Phase 1 — no new test deps. `pytest-asyncio` already configured for async tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 5-posting soft-skill rejection sanity (zero `soft` skills where old prompt would have extracted "communication", "teamwork") | CORP-01 | Live LLM call against ~5 hand-picked postings; flaky for CI; cost ~€0.01 | (1) Pick 5 postings with heavy soft-skill content from `data/postings/`, (2) Run `job-rag reextract --posting-id <uuid>` on each, (3) Query `SELECT skill_name, skill_type FROM job_requirement_db WHERE posting_id IN (...)`, (4) Assert zero rows where `lower(skill_name) IN (REJECTED_SOFT_SKILLS)`. |
| All 108 rows have non-null `skill_category` | CORP-02 | One-shot SQL verification post-reextract | `SELECT skill_category, COUNT(*) FROM job_requirement_db GROUP BY skill_category` — assert 3 rows (hard/soft/domain), no NULL bucket. |
| All 108 rows have ISO-3166 alpha-2 `location_country` (or NULL with `location_region` populated for Worldwide/EU) | CORP-03 | One-shot SQL verification post-reextract | `SELECT COUNT(*) FROM job_posting_db WHERE location_country IS NULL AND location_region IS NULL` — assert 0. Then `SELECT DISTINCT location_country FROM job_posting_db WHERE location_country IS NOT NULL` — assert all 2-char alpha-2 codes. |
| All 108 postings carry the new `prompt_version = "2.0"` | CORP-04 | One-shot SQL verification post-reextract | `job-rag list --stats` — assert output contains `prompt_version=2.0: 108` and no rows with prior version. SQL fallback: `SELECT prompt_version, COUNT(*) FROM job_posting_db GROUP BY prompt_version`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_reextract.py`, `test_lifespan.py` NEW files; existing test files extended)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner finalizes task IDs)

**Approval:** pending
