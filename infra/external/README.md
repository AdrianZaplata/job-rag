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
#   - logout_redirect_uri from same SWA origin (no trailing slash)
```

## Step 2 — Apply

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
