# infra/external/ — Entra External ID app registrations (local-state-only)

Per Phase 4 D-02 (Gap D resolution): this directory manages the SPA + API
app registrations in the Entra External ID (CIAM) tenant. State is LOCAL
and gitignored — there is no CI path because the workforce GHA service
principal cannot auth into the External tenant (AADSTS700016).

## Prerequisites

- Adrian's `az login` against his workforce account with the External-tenant
  admin user role (set up during Phase 3 D-05 manual bootstrap).
- `terraform` ≥ 1.9.
- `infra/bootstrap/` already applied (provides `tenant_id_external` output).
- `infra/envs/prod/` already applied (provides `swa_default_origin` for the
  SPA redirect URI list).

## Step 1 — Prepare tfvars

```bash
cd infra/external
cp terraform.tfvars.example terraform.tfvars.local
# Edit terraform.tfvars.local:
#   - tenant_id_external from `terraform -chdir=../bootstrap output -raw tenant_id_external`
#   - spa_redirect_uris[1] from `terraform -chdir=../envs/prod output -raw swa_default_origin`
```

## Step 2 — Apply

**Phase 04.1-06 refactor —** `infra/external/main.tf` was restructured to use
the `azuread_application_registration` + sibling-resources pattern (replaces
the broken inline-self-reference on the monolithic `azuread_application`).
The three sibling resources now in play are `azuread_application_registration.api`
(lightweight base; carries `requested_access_token_version = 2` as a direct
top-level attribute), `azuread_application_identifier_uri.api` (URI side
resource, cross-references the registration's `client_id`), and
`azuread_application_permission_scope.access_as_user` (carries the OAuth2
scope). On the FIRST apply after this refactor, you will see a destroy/create/replace
cascade — see **"State reconciliation"** below before approving the plan.

```bash
cd infra/external
terraform init
terraform plan -var-file=terraform.tfvars.local
terraform apply -var-file=terraform.tfvars.local
```

First apply takes ~30s. App registrations appear in the Entra portal under
your CIAM tenant → Applications.

## Step 3 — Wire outputs into downstream consumers

```bash
# Option A: manual paste (4 outputs):
terraform output spa_client_id
terraform output api_client_id
terraform output api_audience_uri
terraform output api_scope_name

# Paste into:
#   frontend/.env.production       — VITE_SPA_CLIENT_ID, VITE_API_AUDIENCE
#   infra/envs/prod/prod.tfvars.local — backend_audience, api_audience
#   GitHub repo secrets             — VITE_SPA_CLIENT_ID, VITE_API_AUDIENCE
#
# GitHub:
#   gh secret set VITE_SPA_CLIENT_ID --body "$(terraform output -raw spa_client_id)"
#   gh secret set VITE_API_AUDIENCE  --body "$(terraform output -raw api_audience_uri)"

# Option B: scripted helper
../../scripts/refresh-external-outputs.sh
```

The `scripts/refresh-external-outputs.sh` helper now runs an `az ad app show`
assertion on the live Entra app to guard against the documented silent-fail
mode (memory `terraform-azuread-identifier-uri-unreliable.md`). If the
assertion fires, the script aborts with exit code 2 + a clear unblock
instruction — fix the live state with `az ad app update --identifier-uris ...`
BEFORE downstream files are rewritten.

## Knowingly-accepted security trade-offs

- **Local state**: terraform.tfstate lives in Adrian's working tree; not
  backed up to Azure Storage. Acceptable because v1 is single-user; rebuilding
  app regs from scratch is ~5 min if state is lost. Re-applying with the
  same tfvars regenerates identical resources (idempotent except for the
  `random_uuid.access_as_user_scope_id.result` — re-applying clean state
  generates a new scope UUID; mitigated by committing that one UUID to
  tfvars.local as a one-shot capture if needed).
- **No GHA management**: app regs cannot be CI-managed (Gap D). Every change
  goes through Adrian's local terraform apply + `gh secret set` paste of
  outputs.

## When to re-apply

- Adding a new redirect URI (e.g., a Phase 5 staging env or a new SPA build URL).
- Rotating the `access_as_user` scope (rare).
- Adding a Phase 7 multi-scope flow (e.g., `read:profile` / `write:profile`).

## State reconciliation (Phase 04.1-06 refactor)

On the **first** `terraform apply` after the Phase 04.1-06 split, you will see
this exact destroy/create/replace cascade (verified against the locked
`azuread = 3.8.0` schema via `terraform providers schema -json`):

- **2 to destroy:**
  - `azuread_application.api` — the old monolithic API app reg with the
    broken inline self-reference (`identifier_uris = ["api://${self.client_id}"]`).
    Replaced by the new `azuread_application_registration.api` + sibling resources.
  - `azuread_application_identifier_uri.api` — the current state row points at
    the old base; immediately re-created against the new registration. Same final
    URI value (`api://<new api_client_id>`), different `application_id` reference.
- **3 to add:**
  - `azuread_application_registration.api` — new lightweight base; carries
    `requested_access_token_version = 2` as a direct top-level attribute
    (replaces the old nested `api { requested_access_token_version = 2 }` block
    from `azuread_application.api`). **CIAM rejects v1 tokens** — load-bearing.
  - `azuread_application_identifier_uri.api` — re-created against the new
    registration. Cross-resource reference, plans cleanly.
  - `azuread_application_permission_scope.access_as_user` — new sibling carrying
    the OAuth2 scope (`access_as_user`) that used to live inside the nested
    `api { oauth2_permission_scope { … } }` block on `azuread_application.api`.
- **2 to replace** (each destroy+create — counts as one resource in
  `terraform plan`'s "to replace" line; Terraform v1.9+ rolls these into the
  add+destroy summary):
  - `azuread_service_principal.api` — its `client_id` reference moves from
    `azuread_application.api.client_id` to `azuread_application_registration.api.client_id`;
    the new app registration has a DIFFERENT client_id, so the SP is replaced
    (new `object_id`).
  - `azuread_service_principal_delegated_permission_grant.spa_to_api` — cascades
    from the SP replace; the grant's `resource_service_principal_object_id`
    reference points at the new SP's object_id.
- **1 to change in-place:**
  - `azuread_application.spa` — only the `required_resource_access[0].resource_app_id`
    attribute changes (now points at `azuread_application_registration.api.client_id`).
    The SPA's own `client_id`, `object_id`, redirect URIs, and the SPA SP are
    unchanged.

**Expected `terraform plan` summary line:** `Plan: 3 to add, 1 to change, 2 to destroy, 2 to replace.`
(In Terraform ≥ v1.9, replacements are rolled into the add+destroy totals, so
the actual rendered line is closer to `Plan: 5 to add, 1 to change, 4 to destroy.` —
either rendering is the same plan shape.)

### What changes downstream

The `api_client_id` literal **CHANGES** (a new app registration = a new GUID).
Consequences:

- `frontend/.env.production` `VITE_API_AUDIENCE` becomes `api://<NEW api_client_id>`.
- `infra/envs/prod/prod.tfvars.local` `backend_audience` + `api_audience` become
  `api://<NEW api_client_id>`.
- GitHub repo secret `VITE_API_AUDIENCE` becomes `api://<NEW api_client_id>`
  (run `gh secret set VITE_API_AUDIENCE --body "api://$NEW_API_CLIENT_ID"`).
- The next ACA revision must be restarted to pick up the new `BACKEND_AUDIENCE`
  env value — this is automatic on the next `cd infra/envs/prod && terraform apply`
  because it re-renders the env vars block; alternatively
  `az containerapp revision restart` does it manually.
- Tokens minted against the OLD api_client_id are rejected once the env var
  rolls — but since the OLD app reg is destroyed in this apply, no new tokens
  against the old aud can be minted in the first place.

**The literal STRING SHAPE `api://<guid>` is unchanged.** What changes is the
GUID inside that shape. The load-bearing contract in `src/job_rag/api/auth.py:72`
(`settings.backend_audience.removeprefix("api://")`) is preserved.
`bash scripts/refresh-external-outputs.sh` propagates the new GUID atomically
to every downstream consumer.

### SP-replace cascade — admin consent RE-GRANT (expected, not fallback)

Because `azuread_service_principal.api` is **replaced** (new `object_id`),
the cascade reaches `azuread_service_principal_delegated_permission_grant.spa_to_api`
— Terraform re-creates the grant against the new API SP's `object_id`.
However, `delegated_permission_grant` creates a USER-consent grant by default
(`consentType: Principal` for a specific user). The admin consent granted
via the Entra portal during Phase 4 close-out was tied to the OLD API SP's
`object_id` and **does NOT auto-migrate** to the new SP.

**EXPECT to re-grant admin consent.** This is not a fallback for a broken
step; it is the normal consequence of replacing the SP.

Procedure after `terraform apply`:

1. Open https://entra.microsoft.com in the External (CIAM) tenant context.
2. Navigate: Identity → Applications → Enterprise applications → `jobrag-spa-prod`.
3. Permissions tab → **"Grant admin consent for <External tenant name>"** → confirm.
4. Wait ~30s for replication.
5. Verify: `az ad app permission list-grants --id <SPA SP object_id> -o json | jq` —
   should show `consentType: AllPrincipals` for `access_as_user`.

### Silent-fail mitigation

Silent-fail risk on `azuread_application_identifier_uri` (state says `Created`
while live `identifierUris` stays empty) is now mitigated at the script layer:
`scripts/refresh-external-outputs.sh` runs `az ad app show --query identifierUris -o tsv`
after `terraform output` and exits 2 with an unblock instruction if the live
list is empty. See memory `terraform-azuread-identifier-uri-unreliable.md`.
