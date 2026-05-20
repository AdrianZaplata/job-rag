# Phase 4 Plan 06 — First-login bootstrap runbook

> **Plan:** `04-06-PLAN.md` — Adrian-driven runbook to bridge deploy-ready code (Plans 04-01..04-05)
> into a live, signed-in-end-to-end SPA.
> **Why this is checkpoint-driven, not autonomous:** every step requires Adrian's hands on the
> keyboard — cross-tenant `az login`, real MSAL browser sign-in, OID copy from the live SPA,
> KV secret writes — and per Gap D the workforce-tenant GHA SP cannot auth into the External
> tenant.
> **How to use this file:** Adrian fills observations in-line as the runbook is executed.
> Each checkpoint block has copy-paste-ready command blocks (from the plan) and empty
> `Observed:` / `Output:` placeholders. After all 5 checkpoints close, Claude (next session)
> reads this file to assemble `04-06-SUMMARY.md`.

---

## Status

| Checkpoint | Description                                                                                  | Status         | Closed at |
|------------|----------------------------------------------------------------------------------------------|----------------|-----------|
| 1          | `terraform apply` in `infra/external/` + capture 4 outputs + set 5 GitHub repo secrets       | ⬜ pending      | —         |
| 2          | Fill `prod.tfvars.local` + re-apply `infra/envs/prod/` + verify 4 new ACA env vars           | ⬜ pending      | —         |
| 3          | Trigger `deploy-spa.yml` + first login → land on AccessDenied page with oid                  | ⬜ pending      | —         |
| 4          | `az keyvault secret set` + ACA restart + verify 0005 migration UPDATE landed via psql        | ⬜ pending      | —         |
| 5          | Second login → success path + AUTH-07 hard-refresh + theme/sign-out + optional SSE probe     | ⬜ pending      | —         |

**Started:** _<paste timestamp when Checkpoint 1 begins>_
**Phase 4 close:** _<paste timestamp when Checkpoint 5 closes>_

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
- Cross-tenant constraint memory: `azure-tenant-split.md` (workforce SP cannot auth into External)
- ACA verifier trap memory: `aca-deploy-verifier-trap.md` (per-revision FQDN smoke pattern)

---

## Checkpoint 1 — `terraform apply` in `infra/external/` + capture 4 outputs + 5 GitHub secrets

**Why this requires Adrian's hands on the keyboard:** cross-tenant auth. Only Adrian's local
`az login` session has External-tenant admin permissions (Gap D blocker). The workforce-tenant
GHA SP returns `AADSTS700016` when asked to act against the External tenant.

**Resume signal:** type `outputs-captured` once the 4 outputs are pasted below AND the 5 GitHub
secrets are set, OR describe the apply error.

### Step 1.1 — Verify `az login` points at the workforce account with External-tenant admin

```bash
# At repo root.
az account show --query '{user: user.name, tenantId: tenantId, subscriptionId: id}' -o table
# Expected: user.name = adrianzaplata@gmail.com (or workforce-tenant admin identity)
#           tenantId  = 9a7d79f5-...  (workforce tenant — NOT the CIAM tenant)
```

**Observed:**

```
<paste output of az account show>
```

### Step 1.2 — Prepare tfvars

```bash
cd infra/external
cp terraform.tfvars.example terraform.tfvars.local

# Edit terraform.tfvars.local — fill in:
#   tenant_id_external  = terraform -chdir=../bootstrap output -raw tenant_id_external
#   spa_redirect_uris[1] = "https://$(terraform -chdir=../envs/prod output -raw swa_default_origin)/"
#   logout_redirect_uri  = "https://$(terraform -chdir=../envs/prod output -raw swa_default_origin)"
```

**Helper — read the values out for paste:**

```bash
echo "tenant_id_external  = $(terraform -chdir=../bootstrap output -raw tenant_id_external)"
echo "swa_default_origin  = $(terraform -chdir=../envs/prod  output -raw swa_default_origin)"
```

**Observed (values pasted into `terraform.tfvars.local`):**

```hcl
tenant_id_external  = "<paste GUID>"
spa_redirect_uris   = [
  "http://localhost:5173/",
  "https://<paste swa-default-host>/",
]
logout_redirect_uri = "https://<paste swa-default-host>"
```

### Step 1.3 — `terraform init` + `plan` + `apply`

```bash
cd infra/external
terraform init
terraform plan  -var-file=terraform.tfvars.local
terraform apply -var-file=terraform.tfvars.local
```

**Expected plan shape:** 2 × `azuread_application` (spa + api), 2 × `azuread_service_principal`,
1 × `azuread_application_identifier_uri`, 1 × `azuread_service_principal_delegated_permission_grant`,
1 × `random_uuid`. First apply ~30s.

**Observed:**

```
<paste tail of terraform apply output — last ~20 lines including "Apply complete! Resources: N added, 0 changed, 0 destroyed.">
```

**Apply duration (wall clock):** `<paste>`

### Step 1.4 — Capture the 4 outputs

```bash
cd infra/external
terraform output spa_client_id
terraform output api_client_id
terraform output api_audience_uri
terraform output api_scope_name
```

**Observed outputs (these are the values Plan 04-03 / Plan 04-04 / Plan 04-05 reference):**

| Output            | Value                                                                                         |
|-------------------|-----------------------------------------------------------------------------------------------|
| `spa_client_id`   | `<paste GUID>`                                                                                |
| `api_client_id`   | `<paste GUID>`                                                                                |
| `api_audience_uri`| `api://<paste GUID>`                                                                          |
| `api_scope_name`  | `api://<paste GUID>/access_as_user`                                                           |

### Step 1.5 — Set 5 GitHub repo secrets

```bash
gh secret set VITE_TENANT_SUBDOMAIN --body "$(terraform -chdir=infra/bootstrap output -raw tenant_subdomain)"
gh secret set VITE_TENANT_ID        --body "$(terraform -chdir=infra/bootstrap output -raw tenant_id_external)"
gh secret set VITE_SPA_CLIENT_ID    --body "$(terraform -chdir=infra/external output -raw spa_client_id)"
gh secret set VITE_API_AUDIENCE     --body "$(terraform -chdir=infra/external output -raw api_audience_uri)"
gh secret set VITE_API_BASE_URL     --body "https://$(terraform -chdir=infra/envs/prod output -raw aca_fqdn)"
```

**Verify all 5 secrets exist:**

```bash
gh secret list | grep VITE_
```

**Observed (output of `gh secret list | grep VITE_`):**

```
<paste — should show 5 lines: VITE_TENANT_SUBDOMAIN, VITE_TENANT_ID, VITE_SPA_CLIENT_ID, VITE_API_AUDIENCE, VITE_API_BASE_URL>
```

### Step 1.6 — Refresh `frontend/.env.production` (local-only commit fallback)

```bash
./scripts/refresh-external-outputs.sh
# OR manually edit frontend/.env.production to set the 5 VITE_* values above
```

**Observed (output of refresh script — should print "✓ Updated ..." lines):**

```
<paste script output>
```

### Checkpoint 1 — Done criteria

- [ ] `infra/external/terraform.tfvars.local` exists with all required vars filled
- [ ] `infra/external/terraform.tfstate` exists locally (proves apply succeeded)
- [ ] 4 outputs captured above with matching formats (GUIDs + `api://` URI)
- [ ] 5 `VITE_*` GitHub secrets visible via `gh secret list`
- [ ] `frontend/.env.production` updated (or refresh script run)

**Checkpoint 1 closed at:** `<paste timestamp>`

---

## Checkpoint 2 — Fill `prod.tfvars.local` + re-apply `infra/envs/prod/` + confirm 4 ACA env vars

**Resume signal:** type `prod-applied` once the env-table output is pasted below and the two curl
status codes are recorded.

### Step 2.1 — Create `infra/envs/prod/prod.tfvars.local` (gitignored)

```bash
# Verify gitignored before writing:
git check-ignore -v infra/envs/prod/prod.tfvars.local
# Expected: .gitignore:31:*.tfvars.local  infra/envs/prod/prod.tfvars.local
```

**Contents to paste into `infra/envs/prod/prod.tfvars.local`:**

```hcl
# Phase 4 auth env vars — populated from infra/external/ + infra/bootstrap/ outputs.
# Override the empty placeholders in prod.tfvars.
backend_audience       = "<paste api_audience_uri from Checkpoint 1>"
entra_tenant_id        = "<paste tenant_id_external from infra/bootstrap output>"
entra_tenant_subdomain = "<paste tenant_subdomain from infra/bootstrap output, e.g. 'jobrag'>"

# seeded_user_entra_oid stays empty here — gets filled in Checkpoint 4 via az keyvault secret set.
# The KV secret is what flows to SEEDED_USER_ENTRA_OID env; the tfvar is just the placeholder.
```

**Observed (file content actually written):**

```hcl
<paste verbatim>
```

### Step 2.2 — Re-apply prod

```bash
cd infra/envs/prod
terraform plan  -var-file=prod.tfvars -var-file=prod.tfvars.local
terraform apply -var-file=prod.tfvars -var-file=prod.tfvars.local
```

**Expected plan shape:** modify `azurerm_container_app.api.template.container.env` to set 3 new
plain env entries (`BACKEND_AUDIENCE`, `ENTRA_TENANT_ID`, `ENTRA_TENANT_SUBDOMAIN`). The
`SEEDED_USER_ENTRA_OID` secretRef entry was already wired in Phase 3 (D-09).

**Observed:**

```
<paste tail of terraform apply output — number of resources changed + revision name>
```

### Step 2.3 — Verify ACA env present (the four Phase 4 vars)

```bash
az containerapp show \
  --name jobrag-prod-api \
  --resource-group jobrag-prod-rg \
  --query 'properties.template.containers[0].env[?name==`BACKEND_AUDIENCE` || name==`ENTRA_TENANT_ID` || name==`ENTRA_TENANT_SUBDOMAIN` || name==`SEEDED_USER_ENTRA_OID`].{name:name, value:value, secretRef:secretRef}' \
  -o table
```

**Expected:** 4 rows. `BACKEND_AUDIENCE` / `ENTRA_TENANT_ID` / `ENTRA_TENANT_SUBDOMAIN` show
plain values; `SEEDED_USER_ENTRA_OID` shows `secretRef: seeded-user-entra-oid` (no value).

> Note on ACA app naming: the prod env composition deploys the Container App under the name
> defined in `infra/modules/compute/main.tf`. If `az containerapp show --name jobrag-prod-api`
> returns "not found", try `--name jobrag-api-prod` (some plan docs use that form). Use the
> actual name surfaced by `az containerapp list --resource-group jobrag-prod-rg -o table`.

**Observed:**

```
<paste az containerapp show output — should be 4 rows>
```

### Step 2.4 — Tail ACA logs to confirm restart-on-env-change

```bash
az containerapp logs show --name <aca-name> --resource-group jobrag-prod-rg --follow --tail 50
```

**Expected log sequence:**

- `init_db` runs `alembic upgrade head`; `0005_adopt_entra_oid` is no-op (SEEDED_USER_ENTRA_OID env empty)
- `prompt_version_check_clean` (or `prompt_version_drift` if Phase 2 residuals remain — non-blocking)
- `uvicorn` boots
- `azure_scheme` constructor succeeds (B2CMultiTenantAuthorizationCodeBearer with pinned `openid_config_url`)

**Observed log snippets:**

```
<paste 10-20 lines including alembic + uvicorn startup>
```

### Step 2.5 — Smoke test JWT validation (without a valid token — expect 401)

```bash
ACA_FQDN=$(terraform -chdir=infra/envs/prod output -raw aca_fqdn)

# No Bearer header → 401
curl -s -o /dev/null -w "%{http_code}\n" "https://${ACA_FQDN}/match/test-posting-id"

# Invalid Bearer → 401 (signature/audience rejection)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer invalid-jwt" "https://${ACA_FQDN}/match/test-posting-id"
```

**Observed status codes:**

| Curl                         | Expected | Observed |
|------------------------------|----------|----------|
| No Bearer                    | 401      | `<paste>` |
| Invalid Bearer               | 401      | `<paste>` |

### Checkpoint 2 — Done criteria

- [ ] `infra/envs/prod/prod.tfvars.local` created and gitignored
- [ ] `terraform apply` succeeds in `infra/envs/prod`
- [ ] `az containerapp show` returns 4 env entries (3 plain + 1 secretRef)
- [ ] No-Bearer curl returns 401
- [ ] Invalid-Bearer curl returns 401
- [ ] ACA log line "alembic upgrade head" visible

**Checkpoint 2 closed at:** `<paste timestamp>`

---

## Checkpoint 3 — Trigger `deploy-spa.yml` + first login → land on AccessDenied page with oid

**Resume signal:** type `oid-captured: <oid-value>` once the AccessDenied page shows the oid and
you've copied it (or describe the failure mode).

### Step 3.1 — Trigger `deploy-spa.yml`

**Option A — push:**

```bash
# Edit frontend/README.md "Last deployed" timestamp, commit + push.
# The paths filter in deploy-spa.yml matches frontend/** so a touch to README triggers it.
```

**Option B — manual dispatch:**

```bash
gh workflow run deploy-spa.yml --ref master
```

**Watch the workflow:**

```bash
gh run watch
```

**Observed:**

- Run ID: `<paste>`
- Conclusion: `<paste — should be success>`
- Build duration: `<paste>`
- 5 VITE_* env values resolved at build time? `<paste — check Build step logs for `VITE_API_AUDIENCE: api://...` line if exposed; should NOT print secret values inline>`

### Step 3.2 — Capture the SWA URL

```bash
SWA_ORIGIN=$(terraform -chdir=infra/envs/prod output -raw swa_default_origin)
echo "https://${SWA_ORIGIN}/"
```

**Observed:** `https://<paste>/`

### Step 3.3 — Open SWA URL in a private/incognito window

**Expected sequence:**

1. SPA loads (default-dark theme, blank ~50-150ms for AUTH-07 race fix per CONTEXT.md D-05)
2. `AuthGate` sees no auth → calls `msalInstance.loginRedirect`
3. Browser URL bar transits to
   `https://${VITE_TENANT_SUBDOMAIN}.ciamlogin.com/${VITE_TENANT_ID}/v2.0/oauth2/v2.0/authorize?...`
4. Adrian signs in with his Entra External ID credentials (account created during Phase 3 D-05 manual bootstrap)
5. Browser redirects back to SWA URL + `?code=...&state=...`
6. `main.tsx`'s `await msalInstance.handleRedirectPromise()` (line 19) processes the code → `AppShell` renders
7. Adrian navigates to `/dashboard` → any first API call attaches Bearer → backend returns
   `403 user_not_allowlisted` (SEEDED_USER_ENTRA_OID is still empty in KV)
8. SPA receives 403; Adrian navigates manually to `/access-denied` (per D-09, the AppShell does
   NOT auto-redirect on 403 in v1 — see CONTEXT.md D-09 rationale)
9. `AccessDenied` page renders Adrian's oid in the `<pre>` block via the lazy initializer
   reading `msalInstance.getActiveAccount()?.idTokenClaims?.oid`

### Step 3.4 — Capture observations

**URL bar transit (AUTH-04 verification):**

```
<paste — should include https://<subdomain>.ciamlogin.com/<tenant_id>/v2.0/oauth2/v2.0/authorize?...>
```

**Flash-of-login on first load? (AUTH-07 first verification — should be NO):**

```
<paste — "no flash" or describe what was seen>
```

**DevTools Network tab — first protected API call (after sign-in):**

| Field          | Value                            |
|----------------|----------------------------------|
| URL            | `<paste, e.g. https://<aca-fqdn>/match/<posting_id>>` |
| Method         | `<paste>`                        |
| Status         | `<paste — expected 403>`         |
| Response body  | `<paste — expected {"detail": "user_not_allowlisted"}>` |
| `Authorization` header? | `<paste — should be `Bearer eyJ...`>` |

**AccessDenied page:**

| Element             | Observed                              |
|---------------------|---------------------------------------|
| Heading             | `<paste — expected "Access denied">`  |
| OID in `<pre>` block| `<paste UUID>`                        |
| Copy ID button + toast | `<paste — expected "Copied to clipboard" toast on click>` |

### Step 3.5 — Copy the oid

Click **Copy ID** — expect a sonner toast "Copied to clipboard". Then paste into the field below
for Checkpoint 4.

**Captured oid:** `<paste UUID — this feeds Checkpoint 4 KV secret set>`

### Checkpoint 3 — Done criteria

- [ ] `deploy-spa.yml` run completes with `conclusion=success`
- [ ] SWA URL loads in private window
- [ ] URL bar transits `*.ciamlogin.com` authority during login (AUTH-04 evidence)
- [ ] Post-login, browser returns to SWA + AccessDenied page displays Adrian's oid
- [ ] Copy ID button + toast work
- [ ] OID captured above

**Checkpoint 3 closed at:** `<paste timestamp>`

---

## Checkpoint 4 — `az keyvault secret set` + ACA restart + verify 0005 migration UPDATE landed

**Resume signal:** type `kv-and-update-verified` with the psql output pasted below.

### Step 4.1 — Set the KV secret with the oid captured in Checkpoint 3

```bash
OID="<paste oid from Checkpoint 3>"
az keyvault secret set \
  --vault-name jobrag-prod-kv \
  --name seeded-user-entra-oid \
  --value "$OID"
```

**Expected:** secret version bumps; `az` returns the new secret metadata JSON.

**Observed:**

```
<paste az keyvault secret set output — note the new version GUID + 'updated' timestamp>
```

### Step 4.2 — Restart ACA revision

ACA secret-ref hot-reload is per-revision; explicit restart is the safer path.

```bash
# Find the latest revision name:
REV=$(az containerapp revision list \
  --name <aca-name> \
  --resource-group jobrag-prod-rg \
  --query '[0].name' -o tsv)

az containerapp revision restart \
  --name <aca-name> \
  --resource-group jobrag-prod-rg \
  --revision "$REV"
```

**Observed:**

```
<paste revision restart output>
```

### Step 4.3 — Tail logs during restart

```bash
az containerapp logs show --name <aca-name> --resource-group jobrag-prod-rg --follow --tail 100
```

**Expected log sequence:**

- `init_db` start
- `alembic upgrade head` runs → `0005_adopt_entra_oid` already at head; the migration's
  `os.environ['SEEDED_USER_ENTRA_OID']`-driven UPDATE bridges the seeded user row to Adrian's oid
- `prompt_version_check_clean` (or `prompt_version_drift` — non-blocking)
- `uvicorn` boots
- First subsequent request from Adrian's session → 200 (no `user_not_allowlisted` warning)

**Observed log snippets:**

```
<paste 10-20 lines including the alembic UPDATE + uvicorn ready + first 200>
```

### Step 4.4 — Verify the UPDATE landed via psql

> Prod DB connectivity options: (a) Azure Cloud Shell with auto-AAD auth, (b) psql via Azure DB
> Flex's public endpoint (firewall must include your current IP — see
> `infra/modules/database/README.md` for the home-IP refresh runbook), or (c) `az containerapp
> exec` into the running container and run psql against `$DATABASE_URL`.

```bash
# Option (c) — exec into the container and use the in-container DATABASE_URL.
az containerapp exec \
  --name <aca-name> \
  --resource-group jobrag-prod-rg \
  --command 'psql "$DATABASE_URL" -c "SELECT id, entra_oid FROM users WHERE id = ''00000000-0000-0000-0000-000000000001''::uuid"'
```

> Note on table/column names: Plan 04-02 used `users` (the actual `__tablename__` per
> `src/job_rag/db/models.py::UserDB`) and the row PK column is `id` (the `seeded_user_id` UUID
> `00000000-0000-0000-0000-000000000001`). The migration 0005 UPDATE statement targets exactly
> that row.

**Observed psql output:**

```
<paste output — expected:
   id                                   | entra_oid
 --------------------------------------+--------------------------------------
  00000000-0000-0000-0000-000000000001 | <Adrian's oid captured in Checkpoint 3>
 (1 row)
>
```

**Match check:** does the `entra_oid` value match the oid captured in Checkpoint 3? `<paste — YES/NO>`

### Checkpoint 4 — Done criteria

- [ ] KV secret value matches captured oid (UUID format check)
- [ ] ACA revision restart returns success
- [ ] ACA logs show `alembic upgrade head` + UPDATE for seeded user row
- [ ] psql query returns 1 row with `entra_oid` = captured oid
- [ ] All outputs captured above

**Checkpoint 4 closed at:** `<paste timestamp>`

---

## Checkpoint 5 — Second login → success path + AUTH-07 hard-refresh + theme/sign-out + optional SSE probe

**Resume signal:** type `phase-4-verified` with sign-off notes for AUTH-04, AUTH-07, theme
toggle, sign-out, and (optionally) DebugAgentStream — all observed working, OR describe failures.

### Step 5.1 — Reload SWA URL in private/incognito window (or fresh window)

**Expected:**

- SPA loads
- AuthGate sees existing MSAL session OR triggers loginRedirect (depending on cache state — `sessionStorage` per CONTEXT.md D-06 means tab-close = re-login)
- After sign-in, Adrian lands on `/dashboard` (the redirect from `/`)
- `PhasePlaceholder` for Dashboard renders ("Dashboard coming soon. The dashboard widgets land in Phase 5.")
- DevTools Network tab: no `/access-denied` redirect; no protected route fires in Phase 4 (Phase 5 will exercise this for real)

**Observed:**

```
<paste — landing page, DevTools network summary, any unexpected 403 / redirect>
```

### Step 5.2 — AUTH-07 hard-refresh verification (per VALIDATION.md Manual-Only)

1. Sign in normally and land on `/dashboard`
2. Open DevTools → Network tab → set Throttling = **Slow 3G**
3. Hit `cmd+R` (hard refresh) on `/dashboard`
4. Watch the URL bar throughout the reload

**PASS criterion:** URL bar NEVER transits `*.ciamlogin.com` and the page repaints directly on
`/dashboard` with no visible login-form flash.

**Observed:**

```
<paste — describe URL-bar transit (or absence) + whether any flash appeared. Optional: attach DevTools screenshot.>
```

**AUTH-07 status:** ⬜ PASS / ⬜ FAIL — `<paste>`

### Step 5.3 — AUTH-04 unauth-redirect verification (per VALIDATION.md Manual-Only)

1. Open another fresh private window (no MSAL cache)
2. Navigate to SWA URL
3. Watch URL bar

**PASS criterion:** within ~1s the browser redirects to
`https://${subdomain}.ciamlogin.com/${tenant_id}/v2.0/oauth2/v2.0/authorize?...`

**Observed:**

```
<paste — URL bar transit timing>
```

**AUTH-04 status:** ⬜ PASS / ⬜ FAIL — `<paste>`

### Step 5.4 — OPTIONAL: DebugAgentStream live SSE test

Only if `VITE_DEBUG_PAGES=true` was included in the Checkpoint 1 GitHub secrets (Plan 04-03's
deploy-spa.yml env block includes this flag).

1. Navigate to `/debug/agent-stream`
2. Enter a query (e.g., "what skills appear most often?")
3. Click **Send query**

**Expected event sequence:**

- "connecting" label
- `event: token` lines stream in (incremental tokens)
- `event: tool_start data: {name:'search_jobs', ...}` (tool-call chip)
- `event: tool_end data: {...}` (tool result)
- `event: final data: {reason:'complete'}`
- "--- end of stream ---" separator

This proves Plan 04-04's `readSSEStream` works end-to-end against the live `/agent/stream` SSE
endpoint. Phase 6 chat UI then only writes presentation code.

**Observed (paste event log or N/A):**

```
<paste — or "VITE_DEBUG_PAGES=false in prod; skipped" if Adrian opted out>
```

**DebugAgentStream status:** ⬜ PASS / ⬜ FAIL / ⬜ N/A — `<paste>`

### Step 5.5 — Theme toggle live test

1. Click the Sun/Moon icon in the top-nav
2. Expected: theme flips light↔dark; `localStorage.theme` value updates; refresh persists choice; 150ms cross-fade animation per UI-SPEC §14

**Observed:**

```
<paste — theme transition behavior + localStorage value check (DevTools → Application → Local Storage)>
```

**ThemeToggle status:** ⬜ PASS / ⬜ FAIL — `<paste>`

### Step 5.6 — Sign-out live test

1. Click account dropdown (top-right, User icon) → **Sign out**
2. Expected: redirect to `*.ciamlogin.com` logout endpoint → redirect back to SWA origin → AuthGate triggers loginRedirect again

**Observed:**

```
<paste — URL-bar transit + landing state>
```

**Sign-out status:** ⬜ PASS / ⬜ FAIL — `<paste>`

### Step 5.7 — Phase-close documentation updates (Claude will do this, NOT Adrian)

After Checkpoint 5 closes, the follow-up `gsd-executor` invocation (which reads this RUNBOOK)
will:

- Append a "Phase 4 close" section to `infra/envs/prod/README.md` with the runbook timeline + observed behavior
- Append a "First-login runbook" section to `frontend/README.md` referencing this RUNBOOK
- Update `.planning/STATE.md` to mark Phase 4 status COMPLETE
- Write `.planning/phases/04-frontend-shell-auth/04-06-SUMMARY.md` per the plan `<output>` block
- Mark requirements AUTH-01..07 + SHEL-01/04/05/06 complete in REQUIREMENTS.md
- Update ROADMAP.md Phase 4 progress

### Checkpoint 5 — Done criteria

- [ ] AUTH-04 manually verified (unauth → loginRedirect within 1s)
- [ ] AUTH-07 manually verified (hard refresh on Slow 3G — no flash)
- [ ] Theme toggle + sign-out observed working
- [ ] DebugAgentStream optional test (if enabled) shows live SSE event stream
- [ ] All observations captured above

**Checkpoint 5 closed at:** `<paste timestamp>`

---

## Phase 4 close-out (after Checkpoint 5)

| Total wall-clock time across 5 checkpoints | `<paste>`              |
|--------------------------------------------|------------------------|
| Total cost delta                           | €0 (Entra External free + ACA restart free + KV secret ops free) |
| Phase 4 requirement closure                | 13/13 (SHEL-01..06 + AUTH-01..07) |
| Outstanding follow-ups                     | `<paste any deviations from runbook>` |

**Phase 5 entry point** (per plan `<output>` § Recommended Phase 5 entry point):
`<paste — likely "Plan 05-01 — analytical SQL endpoints (top-skills + salary-bands + cv-vs-market match score)">`

---

*Adrian fills observations in-line as the runbook is executed.*
*Last updated: 2026-05-20 (pre-staged by Claude; Adrian to drive Checkpoints 1-5)*
