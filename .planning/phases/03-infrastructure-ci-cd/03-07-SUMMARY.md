---
phase: 03-infrastructure-ci-cd
plan: 07
subsystem: infra
tags: [smoke-runbook, azure, live-validation, oidc, ghcr, key-vault, postgres, pgvector, log-analytics, cors, sse, ciamlogin]
status: complete

# Dependency graph
requires:
  - phase: 03-infrastructure-ci-cd
    provides: "Plans 02-06 applied stack (bootstrap state, prod composition, ACA + Postgres + KV + LAW + SWA + budget, deploy workflows); Plan 04 federated credentials; Plan 05a/05b prod TF; Plan 06 deploy-api.yml + deploy-infra.yml + deploy-spa.yml"
provides:
  - "03-SMOKE.md as the canonical M1-M13 evidence document for Phase 3"
  - "Verifier-readable mapping DEPL-01..12 -> M{N} -> 03-SMOKE.md section -> 03-UAT.md test row"
  - "Threat coverage table T-3-01..08 -> M{N} mitigation evidence"
  - "Explicit Phase-4 carry-forward boundary for M11 (Entra JWT gate on /agent/stream)"
  - "Cross-reference into Plan 08's defense-in-depth closure (state hygiene via value_wo + KV audit pipe + D-16 amendment)"
affects: [04-msal-auth, 05-dashboard, 06-chat, 08-eval-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Canonical M{N} evidence format: Behavior | Requirement | Threat | Status | Command | Output | Notes (mirrors VALIDATION.md table contract; reusable for future phase smoke runbooks)"
    - "Two-file evidence architecture: SMOKE.md (canonical format projection) + UAT.md (18-test board with Gap tracking) -- both feed one SUMMARY that ties them together for verifier consumption"
    - "Phase-N hand-off boundary documentation pattern: when a requirement is split across phases (M11 SSE pipe in Phase 3, auth gate in Phase 4), the earlier-phase SUMMARY explicitly names the later-phase deliverable instead of leaving the boundary implicit"

key-files:
  created:
    - .planning/phases/03-infrastructure-ci-cd/03-07-SUMMARY.md
  modified: []

key-decisions:
  - "Defer M11 auth-gated streaming half to Phase 4 -- SSE pipe + terminationGracePeriodSeconds=120 are PASS for Phase 3; the Entra JWT gate on /agent/stream is Phase 4 deliverable scope by design"
  - "Use 03-SMOKE.md as the canonical M-ID source-of-truth and reference 03-UAT.md for the 18-test board view -- both files are kept in sync; this SUMMARY links both"
  - "Reference Plan 03-08's defense-in-depth closure (commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6) inside this 07 SUMMARY -- preserves the chronological narrative that 07 smoke ran first, then 08 closed the 3 minor gaps surfaced by the smoke"

patterns-established:
  - "Per-plan SUMMARY responsibility: even when execution evidence lives in a sibling file (03-SMOKE.md), the plan-contract SUMMARY is the canonical entry point. Verifier always reads the SUMMARY first, then follows cross-references to evidence."
  - "Self-Check: PASSED footer pattern (file existence, frontmatter validity, ID-coverage counts) at the tail of every Phase 3 SUMMARY -- cheap pre-commit gate that executor runs before atomic commit lands"

requirements-completed: [DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06, DEPL-07, DEPL-08, DEPL-09, DEPL-10, DEPL-11, DEPL-12]

# Metrics
duration: ~10min
completed: 2026-05-19
---

# Phase 3 Plan 07: Live-Azure Smoke Runbook Summary

**M1-M13 live-Azure smoke executed against the applied prod stack between 2026-05-05 and 2026-05-19 (post-08 closure): all 13 PASS, all 12 DEPL-* requirements covered, all 8 T-3-* threats evidenced, M11's auth-gate half explicitly carried forward to Phase 4. This SUMMARY ties the canonical 03-SMOKE.md evidence to the parallel 03-UAT.md 18-test board (18 PASS / 0 ISSUE post-Plan-08) and references the 03-08 defense-in-depth closure commits.**

## Performance

- **Duration:** ~10min (SUMMARY synthesis); M1-M13 wall-time iteratively captured 2026-05-05 through 2026-05-19 (interleaved with Plan 06 / Plan 08 execution)
- **Started:** 2026-05-19 (SUMMARY synthesis session)
- **Completed:** 2026-05-19
- **Tasks:** 1 (atomic SUMMARY write)
- **Files modified:** 0 (read-only against all phase artifacts); **Files created:** 1 (this SUMMARY)

## Accomplishments

- Plan-contract requirement closed -- `03-07-SUMMARY.md` now exists at the canonical path the plan's `<output>` block declared (`.planning/phases/03-infrastructure-ci-cd/03-07-SUMMARY.md`).
- 12 DEPL-* requirements mapped to M{N} smoke sections via the Requirement Coverage table; every DEPL-* has at least one PASS section, and DEPL-04 carries defense-in-depth coverage across M2/M7/M8/M13 post-Plan-08.
- 8 T-3-* threats mapped to M{N} mitigation evidence via the Threat Coverage table; all three HIGH-severity threats (T-3-01 state hygiene, T-3-02 OIDC trust, T-3-08 CORS bypass) carry direct verification.
- Phase 4 carry-forward documented explicitly -- M11 auth-gated streaming half (Entra JWT on `/agent/stream`) deferred to Phase 4 by design; SSE pipe + grace period are PASS for Phase 3. KV slot `seeded-user-entra-oid` provisioned and reachable for first-MSAL-login OID seeding per D-09.
- Post-smoke defense-in-depth closure cross-referenced -- Plan 03-08 (commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6) closed Gaps 16.A / 10.A / 12.B, advancing UAT from 16/2 to 18/0.
- Phase 3 plan inventory now reads 9/9 SUMMARY files present (01, 02, 03, 04, 05a, 05b, 06, 07, 08) -- phase ready for `/gsd-verify-work 3` and `/gsd-complete-phase 3`.

## Task Commits

Each task was committed atomically on `master`:

1. **Task 1: Synthesize 03-07-SUMMARY.md** -- `<this commit>` (docs) -- commit message `docs(03-07): summarize smoke runbook completion linking SMOKE.md M1-M13 evidence`

_Note: The M1-M13 smoke execution itself produced no source-file commits (the smoke is read-only against the live applied prod stack). The post-smoke gap-closure commits live with Plan 03-08; see Cross-References._

## Files Created/Modified

- `.planning/phases/03-infrastructure-ci-cd/03-07-SUMMARY.md` -- this file; canonical SUMMARY artifact for Plan 03-07. Synthesized from `03-SMOKE.md` (M1-M13 evidence) + `03-UAT.md` (18-test board) + `03-08-SUMMARY.md` (defense-in-depth closure context) + `03-VALIDATION.md` lines 70-89 (canonical M-ID behavior list). No source files modified.

## Requirement Coverage

Mirrors `.planning/phases/03-infrastructure-ci-cd/03-SMOKE.md` Sign-off Requirement Coverage table verbatim. Every DEPL-* requirement has at least one PASS-rated M section.

| Requirement | Covered by                       | Verdict                          |
|-------------|----------------------------------|----------------------------------|
| DEPL-01     | M1                               | PASS                             |
| DEPL-02     | M2                               | PASS                             |
| DEPL-03     | M2                               | PASS                             |
| DEPL-04     | M2, M7, M8, M13                  | PASS (defense in depth post-08)  |
| DEPL-05     | M2, M8                           | PASS                             |
| DEPL-06     | M2, M8                           | PASS                             |
| DEPL-07     | M2, M6, M11                      | PASS                             |
| DEPL-08     | M4, M5, M12                      | PASS                             |
| DEPL-09     | M4                               | PASS (paths-filter contract)     |
| DEPL-10     | M2, M9                           | PASS (post-08 D-16 amendment)    |
| DEPL-11     | M2, M10                          | PASS                             |
| DEPL-12     | M3                               | PASS                             |

## Threat Coverage

Mirrors `.planning/phases/03-infrastructure-ci-cd/03-SMOKE.md` Sign-off Threat Coverage table verbatim. Every T-3-* threat has explicit mitigation evidence in at least one M section; all three HIGH-severity threats (T-3-01, T-3-02, T-3-08) carry direct verification.

| Threat ID   | Category               | Component               | Disposition | Evidence in     | Verdict |
|-------------|------------------------|-------------------------|-------------|-----------------|---------|
| T-3-01 HIGH | Information Disclosure | TF state hygiene        | mitigate    | M13 (post-08)   | PASS    |
| T-3-02 HIGH | Spoofing               | OIDC trust              | mitigate    | M4, M5          | PASS    |
| T-3-03 HIGH | Information Disclosure | Postgres exposed        | accept      | M2, M8          | PASS    |
| T-3-04 MED  | Information Disclosure | GHCR PAT                | mitigate    | M2, M6          | PASS    |
| T-3-05 MED  | Information Disclosure | SWA api_key             | mitigate    | M5              | PASS    |
| T-3-06 MED  | Cost / DoS             | Budget runaway          | mitigate    | M9, M10         | PASS    |
| T-3-07 MED  | Spoofing               | Tenant misconfiguration | mitigate    | M12             | PASS    |
| T-3-08 HIGH | Spoofing               | CORS bypass             | mitigate    | M3              | PASS    |

## Phase 4 Carry-Forward

Two explicit boundary items defer to Phase 4 by design (per CONTEXT.md and the Phase 1 D-09 / D-10 hand-off contracts). Neither is a deviation from Plan 07; both are documented inter-phase boundaries:

- **M11 auth gate on `/agent/stream`** -- Phase 3 verified only the SSE pipe (60-token frame flow, typed `event: token` / `event: final` from `src/job_rag/api/sse.py`) + the static `terminationGracePeriodSeconds=120` ACA config + Test 7's deploy-api.yml drain proof (run 25426147786, full revision swap with workflow's inline 90s `/health` smoke poll passing immediately after activation; no outward-visible disruption). The Entra JWT validation on `/agent/stream` is currently short-circuited by `JOB_RAG_API_KEY=""` per Phase 1 D-10 -- `require_api_key` in `src/job_rag/api/auth.py:7` returns early when the key is empty. Phase 4 will rewrite the `get_current_user_id` body in-place to parse the Entra JWT `sub`/`oid` claim; once Phase 4 wires the JWT gate, the auth-gated streaming half can be re-verified in a Phase 4 SMOKE pass. **Phase 3 does NOT block on it.**
- **KV slot `seeded-user-entra-oid` provisioned + reachable** -- M7 confirms the slot exists in Key Vault and is readable by the ACA system-assigned managed identity (OID `864bcacf-4814-424c-a6e1-0d950a216022`) via `Key Vault Secrets User` data-plane role on `jobrag-prod-kv`. Phase 4 writes the real Entra OID into the slot after the first MSAL login per Phase 1 D-09, then runs `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <real-oid>`. Slot readiness is the Phase 3 deliverable; OID seeding is Phase 4's.

## Decisions Made

- **Defer M11 auth-gated streaming half to Phase 4** -- Plan 07's M11 verifies the SSE pipe + grace-period configuration, which is sufficient evidence for the SSE infrastructure being correct (typed-event contract honored end-to-end; no chunked-encoding stall; no Envoy 502/504). The Entra JWT gate is a Phase 4 deliverable scope (MSAL + token exchange + JWT validation). Trying to verify the auth gate in Phase 3 would require Phase 4 code to be in place, creating a circular dependency. The Phase 1 D-10 forward-compat function-body pattern (`get_current_user_id` returns a Python constant in v1; Phase 4 rewrites the body in-place) is the design that makes this hand-off clean.
- **Use 03-SMOKE.md as the canonical M-ID source-of-truth, reference 03-UAT.md for the 18-test board view** -- The two files serve different audiences: SMOKE.md is the canonical format projection (matches VALIDATION.md M1-M13 contract verbatim; Behavior | Requirement | Threat | Status | Command | Output | Notes per section), while UAT.md is the broader Phase-3-close 18-test board with Gap tracking (UAT Tests 1, 2, 17, 18 cover Phase-3-internal preconditions not in M1-M13). This SUMMARY links both so the verifier and any future reader pick the file that fits the question being asked.
- **Reference Plan 03-08's defense-in-depth closure inside this 07 SUMMARY** -- Plan 07 ran the smoke; Plan 08 closed the three minor gaps the smoke surfaced (Gap 16.A `value_wo` state-hygiene migration; Gap 10.A KV → LAW AuditEvent diagnostic_setting; Gap 12.B D-16 amendment for ACA's binary log pipeline). Cross-referencing 08 from 07 preserves the chronological narrative without conflating the two plans (07 = read-only smoke runbook; 08 = mutating gap closure with TF state changes). Commits 38f06eb (4 envs/prod KV secrets to `value_wo`), 6e31522 (database module `pg_admin_password` to `value_wo`), e02b8f0 (KV diagnostic_setting), 09ca58a (D-16 Amendment), a3d18b6 (prod README Knowingly-Accepted Trade-offs row) are the closure-commit chain.

## Deviations from Plan

None -- this is documentation synthesis from already-captured evidence. The plan-body M1-M13 execution happened iteratively across multiple sessions (2026-05-05 through 2026-05-19); evidence was captured live in `03-UAT.md` at each step, then projected into the canonical `03-SMOKE.md` format on 2026-05-19 (quick task 260519-kr7, commit 317c31c). This SUMMARY closes the plan-contract file-existence requirement.

## Issues Encountered

None during synthesis. The three minor gaps surfaced during the M1-M13 smoke (16.A state hygiene, 10.A KV audit pipe, 12.B D-16 misalignment) were each closed by Plan 03-08 -- see `.planning/phases/03-infrastructure-ci-cd/03-08-SUMMARY.md` for the closure narrative and per-commit detail. The post-08 SMOKE.md verdicts reflect the closed state (M7/M9/M13 carry "post-08" annotations).

Two operational notes worth preserving (not failures, not gaps):

- **First-hour ingestion lag (M7):** Newly-created KV `diagnostic_setting` resources show empty `AzureDiagnostics` rows for ~1h after creation despite verified cold-start exercising all 5 KV reads. Wiring is the verification target (`az monitor diagnostic-settings list` returns 1 entry); runtime audit rows populate on subsequent cold-starts within ~1h. Documented in Plan 08 Task 4 verification block.
- **Cross-region split (M2):** Postgres Flex landed in `northeurope` (`jobrag-prod-pg-ie` suffix) instead of `westeurope` despite `prod.tfvars location='westeurope'`, likely an Azure free-tier Flex availability fallback. ~10ms latency overhead -- accepted; tracked as a future RESEARCH/CONTEXT clarification.

## Cross-References

- **Canonical M1-M13 evidence:** `.planning/phases/03-infrastructure-ci-cd/03-SMOKE.md` (M1 through M13 sections + Sign-off Requirement Coverage + Sign-off Threat Coverage; 655 lines; this is the format-canonical projection of the live-applied evidence).
- **18-test source-of-truth:** `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` (18 PASS / 0 ISSUE as of 2026-05-19 post-Plan-08; UAT Tests 1, 2, 17, 18 cover Phase-3-internal preconditions not in M1-M13).
- **Defense-in-depth closure:** `.planning/phases/03-infrastructure-ci-cd/03-08-SUMMARY.md` (Gaps 16.A / 10.A / 12.B resolved; commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6; Phase 3 UAT advanced from 16/2 to 18/0).
- **Canonical M1-M13 behavior list:** `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md` lines 70-89 (source-of-truth for the M{N} ID definitions + per-row test instructions).
- **Plan contract:** `.planning/phases/03-infrastructure-ci-cd/03-07-PLAN.md` (frontmatter `must_haves`, `requirements: [DEPL-01..12]`, `key_links` pointing at VALIDATION.md M{N} IDs; this SUMMARY closes the plan's `<output>` declaration).

## Push Status

The SUMMARY commit lands locally on `master`. It pushes together with Adrian's next push -- no immediate push is required because the live infrastructure (Plan 02-06 stack + Plan 08 closure) is already updated; this commit is the documentation catch-up. Consistent with Plan 08's Push Status pattern -- live infra changes precede the doc commits that record them.

## Next Phase Readiness

- **Phase 3 fully complete:** 18 PASS / 0 ISSUE on the UAT board; all 12 DEPL-* requirements met (Plan 07 smoke + Plan 08 defense-in-depth); plan inventory 9/9 SUMMARY files present.
- **Phase 4 (MSAL React + Entra JWT validation) unblocked:** Phase 4 hand-off bundle is reachable via `infra/envs/prod/outputs.tf` -- `aca_fqdn` (`jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io`), `swa_default_origin` (`witty-flower-065dac003.7.azurestaticapps.net`), `kv_name` (`jobrag-prod-kv`), `kv_uri` (`https://jobrag-prod-kv.vault.azure.net/`), `tenant_subdomain` (`jobrag`), `tenant_id` (`3fd51a76-f36e-43a1-aa37-564dad4c41fd`), `gha_client_id`, `swa_deployment_token` (sensitive), `seeded_user_entra_oid_secret_name` (`seeded-user-entra-oid`). KV slot `seeded-user-entra-oid` is provisioned + reachable by the ACA managed identity (M7 PASS), ready for first-login OID seeding per Phase 1 D-09.
- **Verifier ready:** Phase 3 ready for `/gsd-verify-work 3` (verifier traces `DEPL-XX -> 03-07-SUMMARY.md frontmatter -> M{N} -> 03-SMOKE.md section -> 03-UAT.md test row` in one hop) and `/gsd-complete-phase 3` (file inventory 9/9 satisfied).

## Self-Check: PASSED

Verified post-write (2026-05-19, before atomic commit):

- `.planning/phases/03-infrastructure-ci-cd/03-07-SUMMARY.md` exists on disk (size > 0).
- Frontmatter parses as valid YAML; all required fields present (phase, plan, subsystem, tags, status: complete, requires/provides/affects, tech-stack, key-files, key-decisions, patterns-established, requirements-completed, duration, completed).
- All 12 DEPL-* IDs (DEPL-01 through DEPL-12) appear in the body's Requirement Coverage table.
- All 8 T-3-* IDs (T-3-01 through T-3-08) appear in the body's Threat Coverage table.
- All 13 M-IDs (M1 through M13) appear in either the Requirement Coverage or Threat Coverage table (or both); M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13 all present.
- Phase 4 Carry-Forward block names both deferred items explicitly (M11 auth gate on `/agent/stream` + KV slot `seeded-user-entra-oid` OID seeding).
- Cross-References block names all 5 sibling files (03-SMOKE.md, 03-UAT.md, 03-08-SUMMARY.md, 03-VALIDATION.md, 03-07-PLAN.md).
- One-liner is substantive (mentions 13 PASS, 12 DEPL coverage, 8 threats, Phase 4 carry-forward, 18/0 UAT post-08) -- not "phase complete" boilerplate.
- No source files modified; this is a documentation-only commit.

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-05-19*
