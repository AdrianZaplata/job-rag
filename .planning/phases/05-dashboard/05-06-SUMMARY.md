---
phase: 05-dashboard
plan: 06
subsystem: testing
tags: [uat, manual-verification, msal, entra-external-id, aca-cold-start, recharts, theme-toggle]

# Dependency graph
requires:
  - phase: 05-dashboard
    provides: 3 widgets (TopSkillsCard, SalaryBandsCard, CvVsMarketCard) + DashboardFilters + useDashboardFilters + 3 /dashboard/* endpoints + analytics service
  - phase: 04-frontend-shell-auth
    provides: AppShell + AuthGate + MSAL + ThemeToggle + authedFetch + Phase 4 D-08 AUTH-06 oid allowlist
  - phase: 03-infrastructure-ci-cd
    provides: live ACA + SWA + Key Vault + deploy-spa.yml + deploy-api.yml
provides:
  - 6 M-marker UAT evidence (M1 initial render, M2 country canary, M3 refresh state, M4 Show More dialog, M5 theme toggle, M6 cold-start)
  - Proof that Phase 5 success criterion #5 (different numbers per country) is satisfied end-to-end
  - 3 hotfix commits (fbf82c6, 8c8037a, ab9437d) landing the iss-subdomain root-cause fix + rate-limit/retry defense-in-depth
  - 2 documented out-of-scope data-quality findings (PLN salary normalization, EU≡WW corpus scope) tracked as Phase 8 polish candidates
  - Auto-memory candidate noted (Entra External ID tenant-GUID iss-subdomain quirk)
affects: [phase-06-chat, phase-07-profile, phase-08-eval-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "UAT.md structure (frontmatter + M-marker tables + Roadmap Success-Criteria Map + Overall Verdict + Deviations)"
    - "uat-screenshots/ gitignored convention (binaries stay local; markdown references paths only)"

key-files:
  created:
    - .planning/phases/05-dashboard/05-UAT.md
    - .planning/phases/05-dashboard/05-06-SUMMARY.md
  modified:
    - .gitignore (added .planning/phases/**/uat-screenshots/ rule)

key-decisions:
  - "Accept ACA cold-start (~225s first-byte after scale-to-zero) as a documented v1 limitation — keeps €0/mo runtime budget per DEPL-03 / Phase 3 D-17. Phase 8 portfolio polish may revisit via min_replicas=1 (~€8/mo continuous warmth)."
  - "Defer Polish PLN salary normalization to v2 per existing PROJECT.md §Constraints decision (treat salaries as EUR in v1). Visible inflated number is tolerable signal to v1 user (Adrian) and doesn't block Berlin/German job-hunt use case."
  - "Track EU ≡ WW corpus-scope finding as Phase 8 polish candidate (cosmetic; country filter is correctly implemented — identical numbers are corpus-distribution artifact, not SQL bug)."
  - "Track N=1 salary-bands rendering as Phase 8 polish candidate (EmptyState chip instead of degenerate Recharts BarChart when postings_with_salary <= 1)."
  - "Retain fbf82c6 (120/min rate limit) and 8c8037a (React Query skip 4xx retries) as defense-in-depth even after ab9437d fixed the root cause — both are correct hardening on their own merit."

patterns-established:
  - "Phase 5 UAT pattern: 6 M-markers + Roadmap Success-Criteria Map + Overall Verdict + Deviations section. Reusable template for Phase 6/7 close-out UATs."
  - "Live-stack root-cause discovery: Phase N's UAT is the first place to catch latent auth bugs from Phase N-1 if Phase N-1's surfaces were placeholders (Phase 4 left iss-subdomain bug latent because /chat and /profile didn't fire authenticated round-trips)."

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, SHEL-03, SHEL-06]

# Metrics
duration: 3min
completed: 2026-05-23
---

# Phase 5 Plan 06: Manual UAT Close-out Summary

**6 M-marker UAT against the live SWA + ACA stack — all 5 ROADMAP Phase 5 success criteria PASS; root-cause auth bug fixed in tree; 2 data-quality findings documented as Phase 8 polish candidates.**

## Performance

- **Duration:** ~3 min (this executor pass — the 6 M-markers themselves spanned 2026-05-22 → 2026-05-23 in real wall-clock time, including the 3 hotfix-and-redeploy cycles)
- **Started:** 2026-05-22T23:57:21Z
- **Completed:** 2026-05-23T00:00:15Z
- **Tasks:** 2 (Task 1 = checkpoint:human-verify executed by Adrian; Task 2 = write UAT.md + SUMMARY.md)
- **Files modified:** 3 (`.planning/phases/05-dashboard/05-UAT.md` created, `.planning/phases/05-dashboard/05-06-SUMMARY.md` created, `.gitignore` patched)

## Accomplishments

- Wrote `.planning/phases/05-dashboard/05-UAT.md` capturing all 6 M-marker results with substantive content (no placeholders): timestamps, observed numerics across PL/DE/EU/WW, screenshots, hotfix commit chronology, deviation triage.
- All 5 ROADMAP.md Phase 5 success criteria recorded as PASS (deep-link filters, top-skills + Show More, salary-bands p25/p50/p75 with N-of-M footnote, CV-vs-market score + missing skills, country-canary).
- Documented 3 hotfix commits (fbf82c6, 8c8037a, ab9437d) and their causal chain — the iss-subdomain mismatch in `_expected_issuer()` was the load-bearing root cause; the rate-limit and React Query retry mitigations remain in tree as defense-in-depth.
- Logged 2 out-of-scope data-quality findings (PLN salary normalization, EU≡WW corpus scope) as Phase 8 polish candidates without expanding Phase 5 scope.
- Added `.planning/phases/**/uat-screenshots/` to `.gitignore` (Phase 5 establishes this convention; Phase 3 had no analog screenshots folder).

## Task Commits

Plan 05-06 has 2 tasks; both are documentation-only:

1. **Task 1: Live UAT against deployed SWA** — Executed by Adrian (checkpoint:human-verify). 9 screenshots saved to `.planning/phases/05-dashboard/uat-screenshots/`. No new commit (verification artifact only; the 3 underlying hotfix commits already landed before this UAT executor pass: `fbf82c6`, `8c8037a`, `ab9437d`).
2. **Task 2: Write 05-UAT.md capturing the 6 M-marker results** — `df542c5` (docs)

**Plan metadata:** to be appended after this SUMMARY.md commit.

## Files Created/Modified

- `.planning/phases/05-dashboard/05-UAT.md` — 6-marker manual UAT evidence (created)
- `.planning/phases/05-dashboard/05-06-SUMMARY.md` — this file (created)
- `.gitignore` — added `.planning/phases/**/uat-screenshots/` rule so binaries stay local (modified)

Screenshots (gitignored — paths referenced from 05-UAT.md):

- `uat-screenshots/m1-dashboard-default.png`
- `uat-screenshots/m2-pl.png`, `m2-de.png`, `m2-eu.png`, `m2-ww.png`
- `uat-screenshots/m3-refresh-state-preserved.png`
- `uat-screenshots/m4-show-more-dialog.png`
- `uat-screenshots/m5-light.png`, `m5-dark.png`

## M-marker Results Table

| Marker | What it verifies | Verdict | Notes |
|--------|------------------|---------|-------|
| M1 | Initial render: 3 widgets show real data; no Skeleton/Alert stuck | **PASS** | Pre-`ab9437d`: 429 cascade. Post-`ab9437d`: clean render. Cold-start matched the documented ~225s baseline. |
| M2 | Country flip canary (PL/DE/EU/WW yields different numbers — success criterion #5) | **PASS** | PL vs DE differ on every column (Top-1 skill count, N postings, p50, mean score, missing must-haves). EU ≡ WW because corpus is EU-only — corpus-distribution artifact, not a SQL bug. |
| M3 | Refresh on deep-linked URL preserves filter state, no login flash | **PASS** | URL identical pre/post refresh; filter UI state restored; no AUTH-07 regression. |
| M4 | Show More dialog opens, scrolls inside dialog body, Escape closes | **PASS** | Dialog overflow rule `max-h-[70vh]` working; row 15 (Kubernetes) confirmed mid-scroll cut. |
| M5 | Theme toggle swaps Recharts chart colors via `var(--chart-1)` | **PASS** | Subtle gray-dark ↔ gray-light swap (radix-nova preset). Cosmetic — Phase 8 candidate to bump `--chart-1` saturation. |
| M6 | Cold-start ACA caveat documented (not fixed) | **DOCUMENTED** | Accept-as-is; €0/mo budget preserved per DEPL-03 / Phase 3 D-17. Phase 8 may revisit. |

## ROADMAP Phase 5 Success-Criteria Map

| Criterion | Marker(s) | Status |
|-----------|-----------|--------|
| #1 Deep-link pre-populates filters; changing filter updates URL | M3 + M2 dashboard interaction | PASS |
| #2 Top-skills widget shows top 8-10 hard skills + Show more drill-down | M1 + M4 | PASS |
| #3 Salary-bands p25/p50/p75 with N-of-M footnote | M1 + M2 | PASS |
| #4 CV-vs-market aggregate score + top-3 missing skills | M1 + M2 | PASS |
| #5 Country flip produces different numbers (SQL flow proof) | M2 | PASS |

## Decisions Made

- **Accept ACA cold-start (~225s) as v1 limitation.** Free-tier €0/mo runtime budget preserved per DEPL-03 / Phase 3 D-17. Phase 8 portfolio polish may revisit via `min_replicas=1` (~€8/mo continuous) once portfolio demo cadence justifies it.
- **Defer Polish PLN salary normalization.** Already documented as v1 limitation in PROJECT.md §Constraints. The inflated PL p50 (€793,440/yr) is a tolerable visible signal; doesn't block Berlin/German target-market use case.
- **Track EU ≡ WW corpus scope as Phase 8 polish candidate.** Cosmetic finding — country filter is correctly implemented (D-07 EU branch covers EU-27 ISO codes + `location_region='EU'` catch-all). Suggested fix: "(corpus is EU-only)" hint under country dropdown.
- **Track N=1 salary-bands rendering as Phase 8 polish candidate.** When `postings_with_salary <= 1`, render EmptyState chip with the literal number instead of degenerate Recharts BarChart.
- **Retain fbf82c6 + 8c8037a in tree as defense-in-depth** even after `ab9437d` fixed the root cause. Rate-limit headroom and React Query 4xx-no-retry are both correct hardening on their own merit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `.planning/phases/**/uat-screenshots/` to `.gitignore`**

- **Found during:** Task 2 (writing UAT.md)
- **Issue:** Plan notes say "uat-screenshots/ subfolder is gitignored by convention (per Phase 3 03-SMOKE.md pattern)" — but no Phase 3 analog folder exists in tree, so the convention was never actually established in `.gitignore`. Without the rule, the 9 PNG binaries (~1.6 MB total) would either be committed in the metadata commit or remain awkwardly untracked.
- **Fix:** Added `.planning/phases/**/uat-screenshots/` rule to `.gitignore` (cohort with the existing `.planning/phases/**/*.local.md` line). 05-UAT.md only references the local paths.
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore .planning/phases/05-dashboard/uat-screenshots/m1-dashboard-default.png` returns the path (PASS).
- **Committed in:** `df542c5` (bundled with the UAT.md commit since they form a single documentation-evidence unit)

---

**Total deviations:** 1 auto-fixed (1 blocking — establishing the gitignore convention)
**Impact on plan:** None on scope. Establishes a reusable convention for Phase 6/7 UATs.

## Issues Encountered

The Plan-2 file-writing pass itself encountered no issues. However, **the Plan-1 (Task 1) human-verify checkpoint surfaced major issues** that landed 3 hotfix commits before UAT could pass:

1. **Initial 429 cascade** (UAT morning attempt, 2026-05-22 ~09:07Z) — Dashboard widgets returned 429 Too Many Requests within ~1–2 minutes of mount. Mitigated by `fbf82c6` (bump per-IP dashboard rate limit 30/min → 120/min) and `8c8037a` (React Query skip 4xx retries). These mitigations were necessary but not sufficient.
2. **Root cause discovered** (2026-05-22, mid-day investigation) — `_expected_issuer()` in `src/job_rag/api/auth.py` was building the expected `iss` claim with the friendly subdomain (`jobrag.ciamlogin.com`), but Entra External ID issues tokens with the tenant GUID as subdomain (`3fd51a76-....ciamlogin.com`). Every authenticated request 401'd → `authedFetch` 401-retry path called `acquireTokenRedirect` → page-level redirect loop → mounted Dashboard fired 3 widget queries per loop iteration → ~39 requests in 3.5s exhausted the rate-limit bucket. Phase 4 left this latent because `/health` is unauthenticated, `/chat` is a Phase 6 placeholder, `/profile` is a Phase 7 placeholder — Phase 5 dashboard is the **first** surface to exercise the full token-acquire-validate roundtrip.
3. **Hotfix landed** — `ab9437d` (`fix(05): use tenant ID as subdomain in iss validation — Entra External ID quirk found in Phase 5 UAT`) committed 2026-05-22 23:06Z. deploy-api.yml took ~226s end-to-end. First successful UAT render at ~23:30Z.

All three commits are in tree as of the UAT pass. `ab9437d` is load-bearing; the other two are correct hardening retained as defense-in-depth.

## User Setup Required

None — no external service configuration required.

## Auto-Memory Candidate

For future Phase 6/7 work (any authenticated surface), add to `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/`:

- **Title:** "Entra External ID `iss` claim uses tenant GUID as subdomain"
- **Content:** Customer tokens from `jobrag.ciamlogin.com` actually embed `iss = https://3fd51a76-....ciamlogin.com/{tenant}/v2.0`, NOT `iss = https://jobrag.ciamlogin.com/{tenant}/v2.0`. `_expected_issuer()` in `src/job_rag/api/auth.py` must match the tenant-GUID form (see commit `ab9437d`). Cross-link: `ciam-customer-vs-b2b-guest.md`.

This complements the existing `ciam-customer-vs-b2b-guest.md` memory entry — that one is about who can sign in; this one is about how their tokens validate server-side.

## Next Phase Readiness

**Phase 5 ships.**

- All 5 ROADMAP.md Phase 5 success criteria verified PASS against the live deployed stack.
- All 6 DASH-* requirements (DASH-01..06) plus SHEL-03 / SHEL-06 are observable in the live UAT M-marker evidence (canonical assertion satisfied).
- Live SPA at https://witty-flower-065dac003.7.azurestaticapps.net/dashboard renders 3 widgets with real Entra-authenticated traffic against a real corpus.

**Parallel-eligible:** Phase 6 (Chat) and Phase 7 (Profile & Resume Upload) can both kick off independently of each other or this phase's verifier pass. Both depend only on Phase 4 (already complete).

**Carry-forward for Phase 8 (Eval & Docs):**

- 4 polish candidates tracked: (a) Polish PLN salary normalization, (b) EU≡WW corpus-scope hint, (c) N=1 salary-bands EmptyState rendering, (d) `--chart-1` saturation bump.
- Cold-start `min_replicas=0` → `min_replicas=1` (~€8/mo) revisit candidate.
- The `ab9437d` `iss`-subdomain root-cause fix is a good DEBRIEF talking point for Phase 8 docs (real-world demonstration of the value of end-to-end UAT against placeholders).

**Blockers / concerns:** none.

## Self-Check

Verifying claims before declaring the plan complete:

- `[ -f .planning/phases/05-dashboard/05-UAT.md ]` → PASS
- `grep -c "^## M" .planning/phases/05-dashboard/05-UAT.md` → 6 (PASS, >= 6)
- `! grep -q "<fill>" .planning/phases/05-dashboard/05-UAT.md` → PASS (no placeholders)
- `grep -q "phase: 5" .planning/phases/05-dashboard/05-UAT.md` → PASS
- `grep -q "Roadmap Success-Criteria Map" .planning/phases/05-dashboard/05-UAT.md` → PASS
- `grep -q "Overall Phase 5 Verdict" .planning/phases/05-dashboard/05-UAT.md` → PASS
- `git log --oneline | grep -q "df542c5"` → PASS (UAT.md commit exists)
- `git check-ignore .planning/phases/05-dashboard/uat-screenshots/m1-dashboard-default.png` → PASS (binaries gitignored)
- `[ -f .planning/phases/05-dashboard/05-06-SUMMARY.md ]` → PASS

## Self-Check: PASSED

---
*Phase: 05-dashboard*
*Completed: 2026-05-23*
*Plan: 06 of 06 (Phase 5 close-out)*
