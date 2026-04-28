# Phase 2 — Corpus Cleanup — Security Audit

**Phase:** 02-corpus-cleanup
**ASVS Level:** L1 (default — `asvs_level: not_specified`)
**Block-on:** critical_only
**Auditor:** gsd-security-auditor
**Date:** 2026-04-28

## Summary

| Metric | Value |
|---|---|
| Threats in register | 16 |
| Disposition: mitigate | 9 |
| Disposition: accept | 7 |
| Disposition: transfer | 0 |
| Closed | 16 / 16 |
| Open | 0 |
| Unregistered flags | 0 |

All mitigation patterns declared in PLAN.md threat models were verified present in implementation files. Accepted-risk threats are logged below per the auditor contract.

## Mitigated Threats — Verification Evidence

| Threat ID | Category | Mitigation Plan | Evidence | Status |
|-----------|----------|-----------------|----------|--------|
| T-02-01-01 | Tampering | Pydantic + ORM rename in lockstep; `test_old_category_field_rejected` catches partial-rename | `src/job_rag/models.py:92-110` (`JobRequirement` with `skill_type` + `skill_category`); `src/job_rag/db/models.py:69-71` (`skill_type` + `skill_category` columns); `tests/test_models.py:41-44` (`test_old_category_field_rejected` raises `ValidationError` on `category=` kwarg) | CLOSED |
| T-02-02-01 | Tampering | `REJECTED_SOFT_SKILLS` is module-constant tuple; `str.format()` placeholder is `{rejected_terms}` only; rejection-terms-in-prompt test exists | `src/job_rag/extraction/prompt.py:27-50` (tuple constant of 22 terms); `src/job_rag/extraction/prompt.py:139-141` (`SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(rejected_terms=...)` — single named placeholder); `tests/test_extraction.py:104-106` (`test_rejected_terms_in_system_prompt` iterates all terms) | CLOSED |
| T-02-03-01 | Tampering | Hand-written migration uses `op.alter_column(new_column_name=...)`, SQL CASE backfill, index swap; smoke tests in `tests/test_alembic.py` | `alembic/versions/0004_corpus_cleanup.py:52-56` (alter_column rename); `:60-63` (drop old index by old name — Pitfall 6); `:68-91` (add nullable → SQL CASE backfill → SET NOT NULL — Pitfall 2); `:76-84` (CASE WHEN skill_type IN ('soft_skill','domain')); `tests/test_alembic.py:67, 149` (`test_0004_upgrade_smoke`, `test_0004_downgrade_smoke`) | CLOSED |
| T-02-03-02 | Repudiation/DoS | `reextract_stale` raises if `all=True` without `yes=True`; CLI uses `typer.confirm` | `src/job_rag/services/extraction.py:72-76` (`if all and not yes: raise RuntimeError`); `src/job_rag/cli.py:321-331` (`typer.confirm` interposed when `--all` without `--yes`; aborts with exit 1 on negative) | CLOSED |
| T-02-03-04 | Tampering | Fresh `AsyncSession` per posting iteration (Pitfall 5) | `src/job_rag/services/extraction.py:82` (Phase 1 SELECT closes its session via `async with`); `:112-114` (loop calls `_reextract_one(pid, report)`); `:142` (each `_reextract_one` opens its own `async with AsyncSessionLocal() as session:`) | CLOSED |
| T-02-03-05 | Tampering | Defensive empty-string→None coercion in `_reextract_one` for all 3 Location fields | `src/job_rag/services/extraction.py:164-169` (`if posting.location.country == "": ... = None` for country/city/region) | CLOSED |
| T-02-03-06 | Information Disclosure | `log.error` uses `error=str(e)`, not full traceback | `src/job_rag/services/extraction.py:121` (outer-loop catch: `error=str(e)`); `:219-223` (inner `_reextract_one` catch: `error=str(e)`). No `traceback`, `exc_info`, or `repr(e)` in either path. | CLOSED |
| T-02-04-01 | Tampering | Per-posting commit + try/except in `_reextract_one`; Pydantic validation in `extract_posting` | `src/job_rag/services/extraction.py:142-223` (per-call `async with AsyncSessionLocal()`; `try: ... except Exception as e: await session.rollback(); report.failed += 1; ...`). `extract_posting` returns Pydantic-validated `JobPosting` (consumer at line 158). | CLOSED |
| T-02-04-02 | Repudiation/DoS | Default selection (not --all) caps work to stale row count; per-posting commit allows Ctrl-C recovery | `src/job_rag/services/extraction.py:88-90` (default branch `WHERE prompt_version != PROMPT_VERSION` — bounded selection); `:206` (`await session.commit()` per-posting before next iteration). SUMMARY 02-04 confirms Ctrl-C recovery worked in practice — original-run hang killed mid-corpus, 55 committed rows preserved, resume picked up only the 53 still-stale rows. | CLOSED |

## Accepted Risks (Disposition: accept)

These threats were declared `accept` in PLAN.md threat models. No code mitigation expected; logged here for audit trail per the auditor contract.

| Threat ID | Category | Component | Acceptance Rationale |
|-----------|----------|-----------|----------------------|
| T-02-01-02 | Information Disclosure | `Location.country` description visible to LLM | "ISO-3166 alpha-2 code" string in `Field(description=...)` propagates into JSON Schema visible to GPT-4o-mini. Intentional grounding (Pitfall 3 mitigation) — no sensitive information leaks. |
| T-02-01-03 | Denial of Service | Pydantic validation on Location | All 3 Location fields nullable (D-09 supports "Worldwide" → country=null). Defensive coercion in `_reextract_one` (T-02-03-05) covers the empty-string LLM quirk. Phase 5 dashboard tolerates surprises by filtering on known countries. |
| T-02-02-02 | Tampering | LLM produces rejected term despite prompt | Prompt-level enforcement is best-effort. Live integration test `TestRejectionRulesLive` validates on real LLM. **Observed:** Plan 04 SQL sanity check found 11 rejected-skill rows leaked across 4 distinct terms (0.56% of total requirements). Documented in 02-04-SUMMARY.md "CORP-01 — FAIL (small leak)". DB-layer post-filter is the documented Phase 5 mitigation. |
| T-02-02-03 | Information Disclosure | Prompt template leaks via error log | If `_SYSTEM_PROMPT_TEMPLATE.format(...)` raises (KeyError on missing placeholder), exception traceback would include template. `test_module_imports_cleanly` proves it doesn't raise. Dev-only surface; no secrets. |
| T-02-03-03 | Information Disclosure | Lifespan drift query log | `log.warning("prompt_version_drift", stale_count=...)` exposes only an integer count (no posting content, no PII, no secrets). |
| T-02-04-03 | Information Disclosure | SUMMARY leaks posting content | Failure strings are `str(e)` — no raw posting content, no PII, no API keys. Adrian's posting corpus is private; SUMMARY stays in `.planning/` (in-repo, not published). |
| T-02-04-04 | DoS | Phase 2 reextract overlaps with `job-rag ingest` | Documented in Plan 03 SUMMARY (Gotcha F): "Run reextract when no other write traffic is in flight." Adrian is single-user; coordination convention, not a technical lock. |

## Unregistered Threat Flags

None. SUMMARY.md `## Threat Flags` sections were not present in any of the four plan summaries (the SUMMARY template's threat-flags section was either absent or empty). No new attack surfaces flagged by the executor that lack a corresponding threat ID.

## Notable Operational Observations (Informational, Not Security Gaps)

These items surfaced in 02-04-SUMMARY.md and are logged for completeness. None constitute security gaps within the threat register.

1. **REJECTED_SOFT_SKILLS leak (CORP-01 FAIL):** 11 rejected-skill rows present in `job_requirements` post-reextract (0.56% of corpus). This is the materialization of the already-accepted T-02-02-02 risk; the threat disposition (accept + Phase 5 DB-layer mitigation) anticipated this exactly. **Not a new gap.**
2. **OpenAI HTTP stall (47-min hang on original reextract run):** No request timeout on the `instructor`/OpenAI client. Resume worked thanks to per-posting commit (T-02-04-02 mitigation operated correctly). 02-04-SUMMARY.md recommends adding `httpx.Timeout` or `asyncio.wait_for(..., 60)` as belt-and-suspenders for Phase 8. Outside Phase 2 scope; **not a Phase 2 threat-register gap.**
3. **Pre-flight `pg_dump` skipped under explicit user authorization** (02-04-SUMMARY.md Deviation 1). Not a security control declared in the threat register; documented manual step only.

## Self-Check

- [x] All `<required_reading>` loaded.
- [x] Threat register extracted from `<threat_model>` blocks across 4 plans (02-01 through 02-04).
- [x] All 9 `mitigate` threats verified by file:line evidence.
- [x] All 7 `accept` threats logged in this SECURITY.md.
- [x] No `transfer` threats in this phase.
- [x] No implementation files modified (read-only audit).
- [x] No unregistered flags found in SUMMARY.md `## Threat Flags` sections.

---

*Phase: 02-corpus-cleanup*
*Audit complete: 2026-04-28*
