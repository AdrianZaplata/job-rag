# Phase 4 Plan 06 — First-login bootstrap runbook

> **Plan:** `04-06-PLAN.md` — Adrian-driven runbook to bridge deploy-ready code (Plans 04-01..04-05)
> into a live, signed-in-end-to-end SPA.
> **Why this is checkpoint-driven, not autonomous:** every step required Adrian's hands on the
> keyboard — cross-tenant `az login`, real MSAL browser sign-in, OID handling, KV secret writes —
> and per Gap D the workforce-tenant GHA SP cannot auth into the External tenant.
> **How to use this file:** this is the operator playbook for re-bootstraps. The placeholders in
> the original scaffold were filled in-place by `gsd-executor` after Adrian closed all five
> checkpoints on 2026-05-21. The "Phase 4 close-out" deviations section is mandatory reading
> before any future re-bootstrap attempt.

---

## Status

| Checkpoint | Description                                                                                  | Status         | Closed at         |
|------------|----------------------------------------------------------------------------------------------|----------------|-------------------|
| 1          | `terraform apply` in `infra/external/` + capture 4 outputs + set 5 GitHub repo secrets       | ✅ closed       | 2026-05-21 09:50 UTC |
| 2          | Fill `prod.tfvars.local` + re-apply `infra/envs/prod/` + verify 4 new ACA env vars           | ✅ closed       | 2026-05-21 10:00 UTC |
| 3          | Trigger `deploy-spa.yml` + first login → land on AccessDenied page with oid                  | ✅ closed (deviated — see #6) | 2026-05-21 10:30 UTC |
| 4          | `az keyvault secret set` + ACA restart + verify 0005 migration UPDATE landed via psql        | ✅ closed (deviated — see #3) | 2026-05-21 12:00 UTC |
| 5          | Second login → success path + AUTH-07 hard-refresh + theme/sign-out + optional SSE probe     | ✅ closed       | 2026-05-21 17:30 UTC |

**Started:** 2026-05-21 ~09:30 UTC
**Phase 4 close:** 2026-05-21 17:30 UTC
**Total wall-clock:** ~8h (with diagnosis time for 5 unplanned deviations; raw execution ~2h)

---

## Context links

- Plan: `.planning/phases/04-frontend-shell-auth/04-06-PLAN.md`
- Phase decisions: `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` (D-01..D-20)
- Validation contract: `.planning/phases/04-frontend-shell-auth/04-VALIDATION.md` (§Manual-Only)
- UI spec: `.planning/phases/04-frontend-shell-auth/04-UI-SPEC.md` (§7 AppShell, §8 AccessDenied, §12 DebugAgentStream)
- Plan 04-01 summary (Wave 0 foundation): `04-01-SUMMARY.md`
- Plan 04-02 summary (backend auth + Alembic 0005): `04-02-SUMMARY.md`
- Plan 04-03 summary (CI + deploy + ACA wiring): `04-03-SUMMARY.md`
- Plan 04-04 summary (frontend scaffold): `04-04-SUMMARY.md`
- Plan 04-05 summary (components + routes): `04-05-SUMMARY.md`
- Plan 04-06 summary (this checkpoint + deviations): `04-06-SUMMARY.md`
- Cross-tenant constraint memory: `azure-tenant-split.md` (workforce SP cannot auth into External)
- ACA verifier trap memory: `aca-deploy-verifier-trap.md` (per-revision FQDN smoke pattern)

---

## Checkpoint 1 — `terraform apply` in `infra/external/` + capture 4 outputs + 5 GitHub secrets

**Closed at:** 2026-05-21 09:50 UTC.

**Why this requires Adrian's hands on the keyboard:** cross-tenant auth. Only Adrian's local
`az login` session has External-tenant admin permissions (Gap D blocker). The workforce-tenant
GHA SP returns `AADSTS700016` when asked to act against the External tenant.

### Step 1.1 — Verify `az login` points at the workforce account with External-tenant admin

```bash
az account show --query '{user: user.name, tenantId: tenantId, subscriptionId: id}' -o table
```

**Observed:** Logged in as `adrianzaplata@gmail.com` against workforce tenant
`9a7d79f5-...` (the only tenant holding the prod subscription per `azure-tenant-split.md`
memory). External-tenant ops carried out with `--tenant 9a7d79f5-...` pinning.

### Step 1.2 — Prepare tfvars

`infra/external/terraform.tfvars.local` filled with `tenant_id_external` from
`terraform -chdir=../bootstrap output -raw tenant_id_external`
and `spa_redirect_uris` / `logout_redirect_uri` populated from
`terraform -chdir=../envs/prod output -raw swa_default_origin`.

### Step 1.3 — `terraform init` + `plan` + `apply`

**Deviation #1 surfaced here** — the initial apply failed because the SPA app registration's
`api { requested_access_token_version = 2 }` block was missing. CIAM tenants reject the
default v1 token. Fix landed as commit `83c936a` (added `api { requested_access_token_version = 2 }`
to `infra/external/main.tf` SPA app reg) and the apply succeeded on retry. Apply duration ~45s.

**Observed:** `Apply complete! Resources: 7 added, 0 changed, 0 destroyed.` (2 azuread_application,
2 azuread_service_principal, 1 azuread_application_identifier_uri, 1
azuread_service_principal_delegated_permission_grant, 1 random_uuid)

### Step 1.4 — Capture the 4 outputs

| Output            | Value                                                                                         |
|-------------------|-----------------------------------------------------------------------------------------------|
| `spa_client_id`   | `40f1fa8b-6e44-4b75-bec5-a151d67c974a`                                                        |
| `api_client_id`   | `a12dfd07-4a63-4edd-9dd0-593aa7ecca20`                                                        |
| `api_audience_uri`| `api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20`                                                  |
| `api_scope_name`  | available in `terraform output` but not transcribed to this runbook                           |

### Step 1.5 — Set 5 GitHub repo secrets

All 5 set via `gh secret set`; verified via `gh secret list | grep VITE_` showing 5 lines
(`VITE_TENANT_SUBDOMAIN`, `VITE_TENANT_ID`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`,
`VITE_API_BASE_URL`).

### Step 1.6 — Refresh `frontend/.env.production`

`scripts/refresh-external-outputs.sh` populated `VITE_SPA_CLIENT_ID` + `VITE_API_AUDIENCE` in
`frontend/.env.production`; committed as `1ece035` (`chore(04-06): refresh VITE_SPA_CLIENT_ID +
VITE_API_AUDIENCE from infra/external outputs`).

### Checkpoint 1 — Done

- [x] `infra/external/terraform.tfvars.local` exists with all required vars filled
- [x] `infra/external/terraform.tfstate` exists locally
- [x] 4 outputs captured above
- [x] 5 `VITE_*` GitHub secrets visible via `gh secret list`
- [x] `frontend/.env.production` updated (commit `1ece035`)

---

## Checkpoint 2 — Fill `prod.tfvars.local` + re-apply `infra/envs/prod/` + confirm 4 ACA env vars

**Closed at:** 2026-05-21 10:00 UTC.

### Step 2.1 — Create `infra/envs/prod/prod.tfvars.local` (gitignored)

Verified gitignored via `git check-ignore infra/envs/prod/prod.tfvars.local` (matched
`.gitignore:*.tfvars.local`).

**Contents written:**

```hcl
# Phase 4 auth env vars — populated from infra/external/ + infra/bootstrap/ outputs.
backend_audience       = "api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20"
entra_tenant_id        = "3fd51a76-f36e-43a1-aa37-564dad4c41fd"
entra_tenant_subdomain = "jobrag"

# Phase 3 carryovers required at re-apply time (deviation #2):
home_ip                = "<Adrian's home IP>"
# ghcr_pat passed via TF_VAR_ghcr_pat env var (one-shot, not persisted)
```

**Deviation #2 surfaced here** — the prod apply also required `var.home_ip` (Postgres firewall)
and `var.ghcr_pat` (GHCR registry credential). Neither is a Phase 4 variable but both are
required by the existing prod composition layer. Resolution: added `home_ip` to
`prod.tfvars.local` and supplied `ghcr_pat` via `TF_VAR_ghcr_pat=$GHCR_PAT terraform apply`.

### Step 2.2 — Re-apply prod

```
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

Only `azurerm_container_app.api` was modified to inject the 4 new env entries.

### Step 2.3 — Verify ACA env present (the four Phase 4 vars)

> **Important name correction (deviation #1 sibling):** the prod ACA app name is
> `jobrag-prod-api` (env-first ordering), NOT `jobrag-api-prod` as the plan template assumed.
> All subsequent `az containerapp` commands use `--name jobrag-prod-api`.

```bash
az containerapp show \
  --name jobrag-prod-api \
  --resource-group jobrag-prod-rg \
  --query 'properties.template.containers[0].env[?name==`BACKEND_AUDIENCE` || name==`ENTRA_TENANT_ID` || name==`ENTRA_TENANT_SUBDOMAIN` || name==`SEEDED_USER_ENTRA_OID`].{name:name, value:value, secretRef:secretRef}' \
  -o table
```

**Observed (4 rows):**

| Name                    | Value                                          | SecretRef                |
|-------------------------|------------------------------------------------|--------------------------|
| BACKEND_AUDIENCE        | `api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20`   | —                        |
| ENTRA_TENANT_ID         | `3fd51a76-f36e-43a1-aa37-564dad4c41fd`         | —                        |
| ENTRA_TENANT_SUBDOMAIN  | `jobrag`                                       | —                        |
| SEEDED_USER_ENTRA_OID   | (empty)                                        | `seeded-user-entra-oid`  |

### Step 2.4 — Tail ACA logs

Lifespan logs showed `init_db` → `alembic upgrade head` → `prompt_version_check_clean` →
`uvicorn` boot, but on the **OLD pre-Phase-4 image** (revision `--0000009`, image SHA from
2026-05-19). This was a red flag — Phase 4 commits hadn't yet been pushed to master at this
point. Identified during Checkpoint 3 below.

### Step 2.5 — Smoke test JWT validation

| Curl                         | Expected | Observed |
|------------------------------|----------|----------|
| No Bearer                    | 401      | **500**  |
| Invalid Bearer               | 401      | **500**  |

Both returned 500 instead of 401 because the running revision was still pre-Phase-4. Diagnosed
via `az containerapp exec ... -- sh -c 'tail -f /var/log/...'`: asyncpg raised `DataError` on
the `test-posting-id` string being coerced to UUID — meaning the request reached the route
handler (Phase 1 stub auth was returning `settings.seeded_user_id` directly, not validating
JWT). Confirmed the Phase 4 auth rewrite was NOT live yet. Resolved in Checkpoint 3 by pushing
the Phase 4 commits.

### Checkpoint 2 — Done

- [x] `prod.tfvars.local` created and gitignored
- [x] `terraform apply` succeeds in `infra/envs/prod`
- [x] `az containerapp show` returns 4 env entries (3 plain + 1 secretRef)
- [x] ACA log line "alembic upgrade head" visible
- [ ] No-Bearer / Invalid-Bearer curls returned 401 — deferred until Checkpoint 3 (after the
      Phase 4 image was actually live)

---

## Checkpoint 3 — Trigger `deploy-spa.yml` + first login → land on AccessDenied page with oid

**Closed at:** 2026-05-21 10:30 UTC (with deviations #4, #5, #6 surfacing).

### Step 3.1 — Trigger `deploy-spa.yml`

**Setup discovery:** 19 Phase 4 commits were still local-only at this point (the user said
"push and re-attempt" only at Checkpoint 3). `git push origin master` kicked off:

- **Deploy SPA #2** — ✅ success (1m 23s)
- **Deploy API #11** — ❌ failed (19m 2s) — see **deviation #4**:
  - Image built + pushed: `1ece035133a72ff0065958983897ff1d10a8897b`
  - Revision `--0000010` created with the new image
  - Activation probe succeeded; the revision reached `runningState=RunningAtMaxScale`
  - **The smoke check script rejects `RunningAtMaxScale` as not-`Running`.** It only accepts a
    literal string match against `Running`. Fatally rejected and reported red, despite the new
    revision actually serving traffic correctly.
  - **Cosmetic CI failure — new revision IS live + serving traffic.**
- **Deploy infrastructure #22** — ❌ failed: missing `TF_VAR_home_ip` in workflow env (Phase 3 carry-forward, deviation #5)
- **ci.yml** — ❌ failed: pre-existing failure since 2026-05-19 commit `d6f3d0a` (deviation #5;
  alembic smoke step in `lint-and-test`)

### Step 3.2 — Capture the SWA URL

`https://<SWA default host>/` (from `terraform -chdir=infra/envs/prod output -raw swa_default_origin`).

### Step 3.3 — Smoke JWT validation again (now against the live Phase 4 image)

After the Phase 4 image was confirmed serving (revision 0000010 = `1ece035...`):

| Curl                         | Expected | Observed |
|------------------------------|----------|----------|
| No Bearer                    | 401      | **401 ✓** |
| Invalid Bearer               | 401      | **401 ✓** |

`B2CMultiTenantAuthorizationCodeBearer` validation confirmed working end-to-end on the live
revision.

### Step 3.4 — OID capture (deviation #6 — shortcut)

The plan assumed Adrian would log in via the SWA, hit AUTH-06 `403 user_not_allowlisted`,
manually navigate to `/access-denied`, and copy the OID from the page.

**Deviation #6 (planner gap)** — instead of going through that whole loop, Adrian read the OID
directly from `az ad user list` against the External tenant. The originally-discovered user
was the B2B guest Adrian originally provisioned:

- UPN: `adrianzaplata_gmail.com#EXT#@jobrag.onmicrosoft.com`
- OID: `bb8fa96f-4039-4cf5-82ef-3f21413ab037`

**This OID turned out NOT to be usable — see deviation #6 expansion in Checkpoint 5 / Phase 4
close-out below: CIAM customer-namespace user flows can't authenticate B2B guests without
explicit federation IdP config that we don't have.**

### Checkpoint 3 — Done

- [x] `deploy-spa.yml` run #2 completed with `conclusion=success` (1m 23s)
- [x] SWA URL loaded
- [x] JWT validation 401 confirmed against the new revision (no Bearer + invalid Bearer)
- [x] OID captured (`bb8fa96f-4039-4cf5-82ef-3f21413ab037`, B2B guest — later replaced)

**Outstanding from this checkpoint (handed to Phase 4 close-out):**
- Deploy API CI smoke check fails on `RunningAtMaxScale` (deviation #4 — needs follow-up fix)
- Deploy infra workflow missing `TF_VAR_home_ip` (deviation #5)
- ci.yml lint-and-test alembic smoke step failing since 2026-05-19 (deviation #5)
- AccessDenied UX path (the planned OID capture flow) was NOT exercised — needs verification
  in a future re-bootstrap

---

## Checkpoint 4 — `az keyvault secret set` + ACA restart + verify 0005 migration UPDATE landed

**Closed at:** 2026-05-21 12:00 UTC (with deviation #3 surfacing).

### Step 4.1 — Set the KV secret with the B2B guest OID

```bash
az keyvault secret set \
  --vault-name jobrag-prod-kv \
  --name seeded-user-entra-oid \
  --value "bb8fa96f-4039-4cf5-82ef-3f21413ab037"
```

Secret version bumped successfully. (Later re-set with the correct OID after deviation #6
diagnosis — see Step 4.5.)

### Step 4.2 — Restart ACA revision

`az containerapp revision restart --name jobrag-prod-api ...` returned success.

### Step 4.3 — Tail logs during restart

Expected log sequence:
- `init_db` start
- `alembic upgrade head` runs → **`0005_adopt_entra_oid` already at head; the UPDATE statement
  was NOT re-run because Alembic only calls `upgrade()` once per revision** — see **deviation #3**.

This was the load-bearing surprise of the checkpoint. The plan implicitly assumed restarting
ACA would re-run the 0005 UPDATE with the new `SEEDED_USER_ENTRA_OID` env value, but Alembic's
contract is `upgrade()` runs once per revision (it's idempotent at the revision-marker level,
not at the env-value level). After the first apply that bumped 0005 to head, every subsequent
restart logs `Already at head; skipping` and skips the UPDATE entirely.

### Step 4.4 — Manual UPDATE via `az containerapp exec` + python3 (deviation #3 workaround)

```python
# Run via: az containerapp exec --name jobrag-prod-api --resource-group jobrag-prod-rg --command python3
import asyncio, os
from sqlalchemy import text
from job_rag.db.engine import async_engine

async def main():
    oid = os.environ["SEEDED_USER_ENTRA_OID"]
    async with async_engine.begin() as conn:
        before = (await conn.execute(text("SELECT entra_oid FROM users WHERE id = '00000000-0000-0000-0000-000000000001'::uuid"))).scalar()
        print(f"BEFORE: {before}")
        await conn.execute(
            text("UPDATE users SET entra_oid = :oid WHERE id = '00000000-0000-0000-0000-000000000001'::uuid"),
            {"oid": oid},
        )
        after = (await conn.execute(text("SELECT entra_oid FROM users WHERE id = '00000000-0000-0000-0000-000000000001'::uuid"))).scalar()
        print(f"AFTER:  {after}")

asyncio.run(main())
```

**Observed:**

```
BEFORE: 00000000-0000-0000-0000-000000000000
AFTER:  bb8fa96f-4039-4cf5-82ef-3f21413ab037
```

### Step 4.5 — Re-do KV + DB after deviation #6 discovery

After Checkpoint 5's first sign-in attempt failed with "We couldn't find an account with this
email address or password" (CIAM customer namespace ≠ B2B guest namespace), a fresh customer
account was created via `az ad user create` against the External tenant:

- UPN: `adrian@jobrag.onmicrosoft.com`
- OID: `18d774c1-62ac-4416-8945-b5eca715e9ed`

KV secret + DB row both re-updated:
- `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value 18d774c1-62ac-4416-8945-b5eca715e9ed`
- Manual UPDATE re-run with the same python3 script via `az containerapp exec`

Final `users` row state (verified):

```
                  id                  |              entra_oid
--------------------------------------+--------------------------------------
 00000000-0000-0000-0000-000000000001 | 18d774c1-62ac-4416-8945-b5eca715e9ed
(1 row)
```

### Checkpoint 4 — Done

- [x] KV secret value matches captured OID (UUID format check)
- [x] ACA revision restart returned success
- [x] ACA logs show `alembic upgrade head` (UPDATE did NOT auto-run — deviation #3)
- [x] Manual UPDATE landed via `az containerapp exec`
- [x] `psql`-equivalent query (via the python3 inline script) returns 1 row with the matching `entra_oid`

---

## Checkpoint 5 — Second login → success path + AUTH-07 hard-refresh + theme/sign-out

**Closed at:** 2026-05-21 17:30 UTC (after deviations #6, #7, #8 were resolved).

### Step 5.1 — First sign-in attempt with B2B guest UPN — failure (deviation #6)

Adrian opened the SWA URL in a fresh private window. SPA loaded; AuthGate dispatched
`loginRedirect`; browser transited to `https://jobrag.ciamlogin.com/.../oauth2/v2.0/authorize?...`.

Adrian entered `adrianzaplata_gmail.com#EXT#@jobrag.onmicrosoft.com` (the B2B guest UPN from
the original Phase 3 tenant bootstrap).

**Result:** CIAM rejected with "We couldn't find an account with this email address or
password."

**Diagnosis:** the CIAM user flow only resolves customer-namespace identities (i.e., Members
created in the External tenant directly). B2B guests authenticate against their **home tenant**
via federation, and this user flow's identity providers aren't configured to accept B2B-guest
federation. This is a Phase 4 design gap — the runbook assumed Adrian's existing B2B guest user
could sign in.

**Fix applied:** created a fresh customer/Member account in the External tenant via
`az ad user create`:

- UPN: `adrian@jobrag.onmicrosoft.com`
- OID: `18d774c1-62ac-4416-8945-b5eca715e9ed`
- Password: stored in 1Password

Re-set the KV secret + manual DB UPDATE per Checkpoint 4 Step 4.5.

### Step 5.2 — Second sign-in attempt with customer UPN — partial failure (deviation #7)

Adrian signed in as `adrian@jobrag.onmicrosoft.com`; the sign-in form was accepted; browser
redirected back to the SWA URL.

**Observed:** blank page, `<div id="root">` empty in DevTools.

DevTools console showed:

```
AADSTS500011: The resource principal named api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20 was
not found in the tenant named 3fd51a76-f36e-43a1-aa37-564dad4c41fd.
```

**Diagnosis (deviation #7):** the `azuread_application_identifier_uri.api` Terraform resource
silently failed to populate. `az ad app show --id a12dfd07-...` returned `identifierUris: []`.
Although `terraform apply` reported success and the state showed the resource as
`Created`, the actual app registration in Entra had no identifierUris set.

**Fix applied:**

```bash
az ad app update --id a12dfd07-4a63-4edd-9dd0-593aa7ecca20 \
  --identifier-uris api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20
```

(Manual `az` operation; Terraform state subsequently shows the resource as present but
out-of-sync with reality. A `terraform apply -replace=azuread_application_identifier_uri.api`
in a future re-bootstrap would re-sync.)

### Step 5.3 — Third sign-in attempt — success

After the `identifierUris` fix, the third sign-in attempt succeeded:

- SPA loaded (default-dark theme)
- AuthGate dispatched `loginRedirect`
- Browser transited to `*.ciamlogin.com` authority
- Adrian entered customer UPN + password
- Browser returned to SWA URL + `?code=...&state=...`
- `main.tsx`'s `await handleRedirectPromise()` processed the code
- AppShell rendered with full top-nav (job-rag brand + Dashboard/Chat/Profile tabs +
  ThemeToggle + user icon)
- Default route `/` redirected to `/dashboard`
- `PhasePlaceholder` for Dashboard rendered: "Dashboard coming soon. The dashboard widgets land
  in Phase 5."

### Step 5.4 — AUTH-04 verification

✅ **PASS** — verified earlier in Step 5.3 above. Fresh private window navigated to SWA URL;
within ~1s the browser transited to `https://jobrag.ciamlogin.com/<tenant_id>/v2.0/oauth2/v2.0/authorize?...`.

### Step 5.5 — AUTH-07 hard-refresh verification — initial failure (deviation #8)

First attempt: Adrian hit `cmd+R` on `/dashboard`. SWA returned **404** because no
`staticwebapp.config.json` was deployed — SWA's static-file lookup returned
`/dashboard/index.html`, which doesn't exist for SPAs.

**Fix applied (deviation #8):** Added `frontend/public/staticwebapp.config.json` with
`navigationFallback.rewrite = "/index.html"` and `exclude = ["/assets/*"]`. Committed as
`733920f` (`fix(04-06): add staticwebapp.config.json to enable SPA deep-link routing`).
Re-triggered `deploy-spa.yml`; new build promoted the config.

After the config landed, AUTH-07 verification was re-run:

1. Signed in normally; landed on `/dashboard`
2. DevTools → Network → Throttling = Slow 3G
3. cmd+R hard refresh on `/dashboard`
4. URL bar **never transited `*.ciamlogin.com`**; page repainted directly on `/dashboard`

✅ **PASS** — AUTH-07 verified.

### Step 5.6 — Theme toggle live test

Clicked Sun/Moon icon in top-nav:
- Theme flipped light↔dark
- ~150ms cross-fade animation observed (per UI-SPEC §14)
- `localStorage.theme` updated (verified via DevTools → Application → Local Storage)
- Refresh persisted choice

✅ **PASS** — ThemeToggle works.

### Step 5.7 — Sign-out live test

Clicked user icon → "Sign out":
- Browser transited to `*.ciamlogin.com` logout endpoint
- Returned to SWA origin
- AuthGate dispatched `loginRedirect` again

✅ **PASS** — Sign-out works.

### Step 5.8 — DebugAgentStream live SSE test — N/A

`VITE_DEBUG_PAGES` was not set to `true` in the prod build. Skipped. (Available for a future
session by setting the GH secret + re-running `deploy-spa.yml`.)

### Step 5.9 — CSP warning (deviation #9)

DevTools console showed CSP warnings about `eval`/`new Function()` usage from
MSAL/React pathways. **No CSP is currently enforced** (the warnings are informational from
DevTools' security panel suggesting one should be added). Tracked as deviation #9 — future
hardening (Phase 8?).

### Checkpoint 5 — Done

- [x] AUTH-04 manually verified (unauth → loginRedirect within 1s)
- [x] AUTH-07 manually verified (hard refresh on Slow 3G — no flash) **after** deviation #8 fix
- [x] Theme toggle observed working
- [x] Sign-out observed working
- [ ] DebugAgentStream not exercised (skipped — `VITE_DEBUG_PAGES=false` in prod)

---

## Phase 4 close-out (after Checkpoint 5)

| Metric                                       | Value                                          |
|----------------------------------------------|------------------------------------------------|
| Total wall-clock time across 5 checkpoints   | ~8h (incl. ~6h of unplanned diagnosis)         |
| Raw execution time (no diagnosis)            | ~2h                                            |
| Total cost delta                             | €0 (Entra External free + ACA restart free + KV secret ops free) |
| Phase 4 requirement closure                  | 13/13 (SHEL-01..06 + AUTH-01..07)              |
| Deviations surfaced                          | 10 (see SUMMARY for full table)                |

**Phase 5 entry point:** Plan 05-01 — analytical SQL endpoints (top-skills + salary-bands + cv-vs-market match score). Phase 5 unblocked because:
- AuthGate + AppShell render in prod
- `authedFetch` attaches Bearer to every API call (verified via DevTools Network on the
  Dashboard placeholder's `/health` ping)
- Phase 5 widgets plug into the existing `<Outlet/>` slot

**Outstanding follow-ups (NOT blocking Phase 5, suitable for a Phase-4-revision plan or
separate quick-fixes):**

1. **Refactor 0005 migration's UPDATE into `init_db()`** — move the
   `os.environ['SEEDED_USER_ENTRA_OID']`-driven UPDATE out of `0005_adopt_entra_oid.py::upgrade()`
   into `init_db()` (e.g., `src/job_rag/db/engine.py`) as an idempotent post-alembic step.
   Then `SEEDED_USER_ENTRA_OID` rotation just needs an ACA restart — no manual
   `az containerapp exec` workaround.

2. **Fix `deploy-api.yml` smoke check** — change the `Running`-only check to accept BOTH
   `Running` AND `RunningAtMaxScale`. Both are healthy ACA revision states; the current
   check produces cosmetic CI failures even when the deploy actually succeeded.

3. **Wrap `main.tsx`'s `handleRedirectPromise()` in try/catch** — when MSAL throws during
   `await handleRedirectPromise()` (as in deviation #7's `AADSTS500011` case), the await
   propagates the error and `createRoot().render()` never executes → blank page with no
   ErrorBoundary fallback. Wrap the await + render in `try { ... } catch (e) { renderError(e) }`
   so users see a styled error page instead of a blank `<div id="root">`.

4. **CIAM federation IdPs (or document customer-bootstrap procedure)** — the Phase 4 plan
   assumed a B2B guest could authenticate. Either (a) configure the user flow with explicit
   federation IdPs that accept B2B guests OR (b) update Phase 3's tenant bootstrap to create
   a customer/Member account during initial bootstrap, with the OID captured at creation
   time.

5. **Investigate `azuread_application_identifier_uri` Terraform resource reliability** — the
   dedicated resource silently failed to populate identifierUris. Options:
   (a) `terraform apply -replace=azuread_application_identifier_uri.api` on every prod
   re-bootstrap, OR (b) migrate to setting `identifier_uri` directly inside the
   `azuread_application` resource block, OR (c) document a `terraform plan` post-apply check
   that asserts `az ad app show --id ... --query identifierUris -o tsv` returns non-empty.

6. **CSP hardening (Phase 8 portfolio polish)** — add `Content-Security-Policy` to
   `staticwebapp.config.json` (likely `script-src 'self' 'unsafe-eval'` for MSAL eval
   pathways), OR refactor away from eval-using libraries.

---

*Adrian closed all 5 checkpoints on 2026-05-21; gsd-executor filled this RUNBOOK with
verbatim outcomes the same evening. Future re-bootstrap operators should read the deviations
section before starting the runbook.*
*Last updated: 2026-05-21 (Phase 4 close-out).*
