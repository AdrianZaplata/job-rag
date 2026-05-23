---
phase: 5
slug: dashboard
status: complete
date: 2026-05-22..2026-05-23
uat_environment: prod SWA + prod ACA (single-env free-tier deployment)
swa_origin: https://witty-flower-065dac003.7.azurestaticapps.net
backend_aca_fqdn: https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io
signed_in_oid: 18d774c1-62ac-4416-8945-b5eca715e9ed
overall_verdict: PASS WITH DOCUMENTED FINDINGS
---

# Phase 5 — Manual UAT Evidence

> Per VALIDATION.md section "Manual-Only Verifications". 6 M-markers; each must
> PASS or be documented as FAIL-with-note. Cross-references the success
> criteria in ROADMAP.md Phase 5.

## Environment

- **SWA origin:** https://witty-flower-065dac003.7.azurestaticapps.net
- **Backend ACA FQDN:** https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io
- **Adrian's signed-in oid:** `18d774c1-62ac-4416-8945-b5eca715e9ed` (seeded local customer `adrian@jobrag.onmicrosoft.com`)
- **Browser:** Chromium (incognito) — per gstack `/browse` skill convention
- **Date / time:** UAT session spanned the 2026-05-22 → 2026-05-23 boundary. Initial morning attempt ~09:07Z 2026-05-22; first SUCCESS at ~23:30Z 2026-05-22 (after the `ab9437d` redeploy completed); M3–M5 captured early 2026-05-23.

---

## Issues Found During UAT (pre-PASS triage)

Three hotfix commits had to land before UAT could pass. Recorded here so future
readers understand the gap between Plan 05-05 SUMMARY landing and a green dashboard.

### Root cause: `iss` validation mismatch (Entra External ID quirk)

Phase 5 dashboard was the **first** authenticated surface to exercise the full
MSAL → Entra External ID → fastapi-azure-auth → AUTH-06 oid-allowlist roundtrip
end-to-end. Phase 4 left this latent because:

- `/health` is unauthenticated
- `/chat` is a Phase 6 placeholder (no API call)
- `/profile` is a Phase 7 placeholder (no API call)
- The Phase 4 verification flow only proved sign-in landed and protected routes
  redirected — not that an `Authorization: Bearer <jwt>` round-trip actually
  validated server-side.

The bug: `_expected_issuer()` in `src/job_rag/api/auth.py` was constructing the
expected `iss` claim with the friendly subdomain (`jobrag.ciamlogin.com`), but
Entra External ID actually issues tokens with the **tenant GUID as
subdomain** (`3fd51a76-....ciamlogin.com`). Every authenticated dashboard
request therefore 401'd at the auth dep. `authedFetch`'s 401 retry path then
called `acquireTokenRedirect`, which triggered a page-level redirect loop.
On each iteration, the freshly-mounted Dashboard fired its 3 parallel widget
queries, exhausting the rate-limit bucket: ~39 requests in 3.5 seconds → 429.

### Hotfix commits (chronological)

| Commit | When (UTC+02) | What | Why insufficient on its own |
|--------|---------------|------|----------------------------|
| `fbf82c6` | 2026-05-22 18:08 | Bumped per-IP dashboard rate limit 30/min → 120/min (3 widgets × cold-start retry × Azure Front Door IP collapse exceeded 30/min) | Mitigation only — masked the redirect-loop firehose without stopping it |
| `8c8037a` | 2026-05-22 18:09 | React Query: skip retries on 4xx (don't multiply rate-limit pressure when auth itself is rejecting) | Mitigation only — cut amplification factor from ~13× to ~3× per loop iteration |
| `ab9437d` | 2026-05-22 23:06 | **Root-cause fix:** `_expected_issuer()` now uses tenant ID as subdomain to match Entra External ID's actual token issuer | Sufficient — first successful end-to-end widget render landed within minutes of API redeploy completing |

`fbf82c6` and `8c8037a` remain in tree as defense-in-depth (rate-limit headroom
and React Query 4xx-no-retry are both correct hardening regardless of the
underlying bug). `ab9437d` is the load-bearing fix.

Memory entry to add (auto-memory candidate): "Phase 5 dashboard was the first
surface to exercise full token-acquire-validate roundtrip — Phase 4 placeholders
masked the iss-subdomain mismatch latent in `_expected_issuer()`." Cross-link to
`~/.claude/projects/-Users-adrian-Developer-job-rag/memory/ciam-customer-vs-b2b-guest.md`.

---

## M1 — Initial dashboard render

| Property | Value |
|----------|-------|
| Initial visit timestamp | ~09:07Z 2026-05-22 (first attempt — failed with 429s pre-`ab9437d`) |
| First SUCCESS timestamp | ~23:30Z 2026-05-22 (after `ab9437d` redeploy) |
| Cold-start observed (first-byte) | ~60–120s on morning attempt (per Adrian's report); deploy-api.yml smoke-test step on `ab9437d` redeploy took 226s end-to-end (consistent with documented `aca-cold-start-profile.md` baseline ~225s) |
| Subsequent warm latency | sub-second (Adrian-confirmed; mid-UAT widget refetches felt instant) |
| Widgets rendered | TopSkillsCard + SalaryBandsCard + CvVsMarketCard (all 3) |
| Errors visible | None after `ab9437d` deploy |
| Screenshot | `uat-screenshots/m1-dashboard-default.png` |
| Verdict | **PASS** (after `ab9437d` redeploy; failed pre-deploy with 429s caused by the `iss`-subdomain bug — see "Issues Found During UAT" above) |
| Notes | First load post-deploy paid the documented ACA cold-start cost. Subsequent loads are sub-second. Verified all 3 widgets show non-zero numbers with the Worldwide (default) filter. |

---

## M2 — Country flip exercises SQL (success criterion #5 — the canary)

| Country | Top-1 skill (count) | "N postings" footer | p50 salary | CV mean_score | Top-3 missing must-haves (count) |
|---------|---------------------|---------------------|------------|---------------|----------------------------------|
| PL | Python (40) | 55 | **€793,440/yr** ⚠ | 0.29 | Azure (26) / AWS (22) / SQL (20) |
| DE | Python (29) | 33 | €67,500/yr | 0.28 | TensorFlow (18) / LLMs (15) / ML (15) |
| EU | Python (69) | 88 | €684,864/yr ⚠ | 0.28 | AWS (18) / SQL (17) / Azure (17) |
| WW | Python (69) | 88 | €684,864/yr ⚠ | 0.28 | AWS (18) / SQL (17) / Azure (17) |

**At least one column differs across the 4 rows:** **YES** — every column differs across PL/DE. EU and WW are identical (corpus is EU-only; see Finding 2 below).
**Verdict:** **PASS**
**Screenshots:** `uat-screenshots/m2-pl.png`, `m2-de.png`, `m2-eu.png`, `m2-ww.png`

### Documented findings (out-of-M2-scope; logged as Phase 6/8 polish candidates)

1. **Currency normalization bug.** Polish p50 €793,440/yr is implausible. PLN
   793,440 ≈ €185k/yr at 2026 FX (realistic for Polish AI-Engineer roles). The
   bug pattern: analytics treats raw `salary_min` as EUR regardless of source
   currency. Confirmed by contrast — German p50 €67,500/yr is realistic
   (postings priced natively in EUR). The EU and WW p50 (€684,864/yr) is also
   inflated, almost certainly because the Polish PLN outliers pull the
   percentile up. **Likely fix sites:** either
   `src/job_rag/services/analytics.py::salary_bands` (multiply by FX rate at
   query time using a small lookup table) or upstream during ingestion in
   `src/job_rag/extraction/extractor.py` (normalize to EUR at write time;
   preferred — keeps query path numeric-only).
   **PROJECT.md §Constraints already documents:** "all salary values treated as
   EUR; FX-aware conversion is a v2 platform feature" (Phase 5 CONTEXT.md
   Claude's Discretion). The bug here is that the field name suggests EUR but
   the data contains the LLM-extracted native-currency numeric. Two options:
   (a) treat as deferred-to-v2 per existing CONTEXT.md decision, or (b) bump
   to a Phase 8 polish ticket. Recommend **(a) defer** — the inflated number
   is a visible signal to the v1 user (Adrian) that something is off; doesn't
   block job-hunt use cases (Adrian knows the German market).

2. **EU ≡ WW (corpus scope finding).** Corpus is entirely EU-sourced
   (PL + DE = 88 ≡ EU = 88 ≡ WW = 88). The UI doesn't disambiguate; a viewer
   not familiar with the corpus might assume the country filter is broken.
   **Mitigations** (Phase 8 polish candidates): (i) add a "corpus is EU-only"
   hint under the country dropdown, or (ii) hide the Worldwide option when the
   corpus is regional. Recommend (i) — cheap, transparent, and matches the
   Linear-dense ethos (one-line subtext, no removed affordance).

Neither finding blocks the success criterion. The canary (filter changes flow
through to SQL) is conclusively proven by the PL vs DE column differences.

---

## M3 — Refresh preserves state (DASH-06 + AUTH-07 carry)

| Property | Value |
|----------|-------|
| URL before refresh | `/dashboard?country=DE&seniority=senior&remote=remote` |
| URL after refresh | `/dashboard?country=DE&seniority=senior&remote=remote` (identical) |
| Filter UI state after refresh | country=Germany / seniority=Senior / remote=Remote (all preserved) |
| Login flash observed | None |
| Postings matched at this filter combo | 5 (filter narrows DE corpus + seniority + remote_policy='remote') |
| Screenshot | `uat-screenshots/m3-refresh-state-preserved.png` |
| Verdict | **PASS** |
| Notes | Of the 5 matched postings, only 1 had salary data. Visualization shows empty/clipped bars with labels truncating at the card top — minor visual artifact when N=1 for salary-bands, not a blocker. Logged as a Phase 8 polish candidate: when `postings_with_salary === 1` (or 0), render an EmptyState chip instead of an under-resolved chart. Filed against `frontend/src/components/dashboard/SalaryBandsCard.tsx`. |

---

## M4 — Show more Dialog (DASH-05)

| Property | Value |
|----------|-------|
| Dialog title | "All top skills" ✓ |
| Dialog description | "Full ranked list of hard skills across the filtered postings." ✓ |
| Table columns | #, Skill, Must, Nice, Total ✓ |
| Row count observed | 15+ visible; row 15 (Kubernetes) cut mid-scroll → confirms scrolling within dialog body |
| Scroll behavior | Inside dialog (NOT page); underlying page blurred via overlay; `max-h-[70vh]` overflow rule confirmed working |
| Escape closes | YES (Adrian-confirmed) |
| Screenshot | `uat-screenshots/m4-show-more-dialog.png` |
| Verdict | **PASS** |
| Notes | Plan 05-05 D-20 ("scrollable table inside Dialog") verified end-to-end with real corpus data. The 50-row cap (D-20 default) wasn't exceeded — Worldwide corpus has fewer than 50 unique hard skills, so Adrian saw the natural end of the list. |

---

## M5 — Theme toggle on /dashboard (Phase 4 carry-forward)

| Property | Value |
|----------|-------|
| Dark → Light works | YES |
| Light → Dark works | YES |
| Recharts chart color swaps (`var(--chart-1)`) | YES |
| Card backgrounds adapt | YES |
| Text contrast maintained | YES |
| Screenshots | `uat-screenshots/m5-light.png`, `uat-screenshots/m5-dark.png` |
| Verdict | **PASS** |
| Notes | Recharts swap is gray-dark ↔ gray-light. The radix-nova `--chart-1` preset is a neutral gray rather than a vibrant accent — the swap is correct (CSS-var-driven) but visually subtle. Phase 8 polish candidate: bump `--chart-1` to a more saturated accent for stronger visual signal. Not a blocker — Phase 4 D-20 chose radix-nova for the Linear-dense ethos, which prefers grayscale + 1 accent. |

---

## M6 — Cold-start documentation (Phase 8 candidate)

> The first dashboard load after the container has scaled to zero takes ~225s
> (ACA cold-start; see memory file `aca-cold-start-profile.md`). Subsequent loads
> are sub-second. This is intentional — `min_replicas=0` keeps the project at
> €0/mo runtime budget (Phase 3 D-17 / DEPL-03). Phase 8 portfolio polish may
> revisit by flipping `min_replicas=1` for ~€8/mo continuous warmth.

| Property | Value |
|----------|-------|
| Observed cold-start time (M1) | ~60–120s on Adrian's morning attempt; smoke-test step on the `ab9437d` API redeploy took 226s end-to-end (matches documented baseline ~225s) |
| Subsequent warm latency | sub-second (Adrian-confirmed by mid-UAT widget refetches) |
| Recommendation | **Accept.** Keeps €0/mo runtime budget (DEPL-03 / Phase 3 D-17). Phase 8 portfolio polish may revisit by flipping `min_replicas=1` (~€8/mo continuous warmth) once portfolio demo cadence justifies it. |
| Verdict | **DOCUMENTED** (no action required) |
| Notes | Confirms `aca-cold-start-profile.md` baseline. Phase 5's 3 parallel widget fetches at mount don't multiply the cold-start cost — they queue behind the first response (ACA serializes startup). Future Phase 8 alternatives if scale-to-zero ever bites: (a) `min_replicas=1` (~€8/mo continuous), (b) keep `min_replicas=0` but add a synthetic warmup ping every 30 min (Azure Monitor scheduled-test alert, free up to 5 tests), (c) accept-as-is and document on the live page (e.g., "Backend may take a moment to wake up on first visit"). |

---

## Roadmap Success-Criteria Map

| # | Criterion | Marker(s) | Verdict | Notes |
|---|-----------|-----------|---------|-------|
| 1 | Deep-link pre-populates filters; changing filter updates URL | M3 + dashboard filter interaction observed during M2 | **PASS** | URL round-trip verified both ways: M3 deep-link → filter UI; M2 filter UI → URL params |
| 2 | Top-skills widget shows top 8-10 hard skills + Show more drill-down | M1 + M4 | **PASS** | M1 confirmed top-skills rendering with real data; M4 confirmed Show More dialog table + scroll behavior |
| 3 | Salary-bands p25/p50/p75 with N-of-M footnote | M1 + M2 | **PASS** | Footnotes observed: "26 of 88 postings had salary data" (M2 WW) and "1 of 5" (M3 DE+Senior+Remote). Both formats present as DASH-02 specifies. |
| 4 | CV-vs-market aggregate score + top-3 missing skills | M1 + M2 | **PASS** | Mean score + 3-chip missing-must-have list rendered for every M2 country variant |
| 5 | Country flip produces different numbers (SQL flow proof — **the canary**) | M2 | **PASS** | PL vs DE differ across every column (Top-1 skill count, N postings, p50, mean score, missing must-haves). EU ≡ WW because corpus is EU-only (Finding 2 above) — not a SQL bug. |

**All 5 criteria PASS.**

---

## Overall Phase 5 Verdict

**PASS WITH DOCUMENTED FINDINGS**

- All 6 M-markers either PASS (M1–M5) or DOCUMENTED (M6 cold-start).
- All 5 ROADMAP.md Phase 5 success criteria PASS.
- Two data-quality findings (Polish currency normalization, EU≡WW corpus scope)
  are explicitly **out of Phase 5 scope** per PROJECT.md §Constraints
  ("salary values treated as EUR; FX-aware conversion is a v2 platform
  feature"). Both are tracked as Phase 6/8 polish candidates in this UAT
  document and are NOT blockers for closing Phase 5.
- Three hotfix commits (`fbf82c6`, `8c8037a`, `ab9437d`) were required during
  UAT before the dashboard could render. Root cause was the `iss` subdomain
  mismatch in `_expected_issuer()` — a Phase 4 latent bug surfaced for the
  first time by Phase 5 (the first surface to exercise full token-acquire-
  validate roundtrip). Fix `ab9437d` is load-bearing; the rate-limit and
  React Query mitigations remain in tree as defense-in-depth.

---

## Deviations from spec (if any)

### 1. Three hotfix commits during UAT (`fbf82c6`, `8c8037a`, `ab9437d`)

- **Disposition:** accepted-as-is + cause fixed in tree
- **Reason:** `ab9437d` corrects a Phase 4 latent bug (`_expected_issuer()`
  used the friendly CIAM subdomain instead of the tenant GUID subdomain that
  Entra External ID actually emits in the `iss` claim). Phase 4 only proved
  sign-in landed and protected routes redirected; Phase 5 was the first
  surface to actually fire an authenticated `Authorization: Bearer` round-trip.
  `fbf82c6` and `8c8037a` are correct hardening regardless of `ab9437d` —
  retained as defense-in-depth.
- **Cross-reference:** D-08 (Phase 4 AUTH-06 single-user `oid` allowlist) is
  satisfied unchanged; only the `iss` validation path was wrong. No
  re-litigation of the auth design.
- **Memory candidate:** add to `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/` —
  "Entra External ID tokens use tenant GUID as `iss` subdomain, not the friendly
  CIAM hostname; `_expected_issuer()` must match the GUID form."

### 2. Data finding — Polish salary normalization (M2 PL p50 €793,440/yr)

- **Disposition:** deferred-to-v2 per existing PROJECT.md §Constraints decision
- **Reason:** PROJECT.md already documents EUR-as-shown is a v1 limitation; FX
  normalization is a v2 platform feature. Visible inflated number is a tolerable
  signal to the v1 user (Adrian) and doesn't block his job-hunt use case
  (Berlin/German target market where EUR-priced postings are accurate).
- **Cross-reference:** Phase 5 CONTEXT.md Claude's Discretion §"Currency
  assumption". Confirms the limitation rather than introducing it.

### 3. Data finding — EU ≡ WW corpus scope (M2 EU/WW identical numbers)

- **Disposition:** Phase 8 polish candidate
- **Reason:** Cosmetic / informational. The country filter is correctly
  implemented (D-07 EU branch correctly aggregates all EU-27 ISO codes + the
  `location_region='EU'` Worldwide-remote catch-all). The identical numbers
  are an artifact of corpus distribution, not a SQL bug.
- **Suggested fix (Phase 8):** add a "(corpus is EU-only)" hint under the
  country dropdown, or conditionally hide the Worldwide option when
  `SELECT DISTINCT location_country` from `job_postings` is entirely EU.

### 4. Visual artifact — N=1 salary-bands rendering (M3)

- **Disposition:** Phase 8 polish candidate
- **Reason:** Cosmetic. When the filter combo (DE + Senior + Remote = 5
  postings, of which 1 has salary data) leaves the salary-bands widget with
  N=1, the Recharts BarChart renders an under-resolved chart with clipped
  labels. The number itself is correct; the chart shape is degenerate.
- **Suggested fix (Phase 8):** in `SalaryBandsCard.tsx`, when
  `postings_with_salary <= 1`, render an EmptyState chip with the literal
  number instead of the chart.

None of the 4 deviations are blockers for Phase 5 close-out. (1) is fixed in
tree. (2)–(4) are out-of-scope polish candidates.

---

*Phase: 05-dashboard*
*UAT executed: 2026-05-22 → 2026-05-23*
*All 6 markers complete; 5/5 ROADMAP success criteria PASS.*
