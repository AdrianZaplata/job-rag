# Infra Bootstrap

> One-time, runs LOCAL state. Creates the Azure Storage account that hosts state for `infra/envs/{prod,dev}/`. The Entra External tenant is also imported here (manually created via portal first per D-05; Microsoft has no first-class Terraform resource for tenant creation in `azuread ~> 3.x`).

**Last verified:** 2026-04-29 (External Identities admin UX is changing fast — re-verify before each run, see PITFALLS §1)

---

## Prerequisites

- Adrian's local machine has Terraform 1.9+ installed (`brew install terraform` / `choco install terraform`).
- Adrian is signed in to `az` CLI with an account that has **Owner** role on the target subscription (`az login` then `az account set --subscription "<sub-id>"`).
- Adrian's account has the **Tenant Creator** role on the directory (default for the subscription owner; if missing, request from the directory admin).

## Step 1 — Create the Entra External tenant (manual portal click-path, ~5 min)

1. Sign in at https://entra.microsoft.com/.
2. **Identity → Overview → Manage tenants** (top of page) → **+ Create**.
3. Tenant type: **External** (NOT Workforce, NOT B2C — PITFALLS §1).
4. Fill the form:
   - **Tenant name:** `Job RAG External`
   - **Initial domain name:** `jobrag` (becomes `jobrag.ciamlogin.com` — the MSAL authority Phase 4 will use)
   - **Country/Region:** `Germany` (or wherever Adrian's Azure subscription home is)
   - **Subscription:** Adrian's existing Azure subscription
   - **Resource group:** create new `jobrag-extid-rg` in `westeurope`
5. **Review + Create** → **Create**. Provisioning takes ~2-3 minutes.
6. Switch to the new tenant from the directory selector. Capture from `Overview`:
   - **Tenant ID (GUID)** — e.g. `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`
   - **Primary domain** — should be `jobrag.ciamlogin.com`

## Step 2 — Run bootstrap Terraform

```bash
cd infra/bootstrap

# Provide the tenant ID captured in Step 1.
# Use a *.tfvars.local file (gitignored) or pass -var on the command line.
cat > terraform.tfvars.local <<EOF
tenant_id_external = "<paste tenant GUID from Step 1>"
tenant_subdomain   = "jobrag"
EOF

# Initialize providers (no backend — local state on purpose).
terraform init -backend=false

# Apply — creates RG + storage account + container + locks in tenant variables.
# Also grants the apply principal (Adrian) "Storage Blob Data Contributor" on the
# tfstate container so the AAD-auth backend in infra/envs/prod/ can read/write
# state. (Disabling shared-key auth on the storage account is deferred — see the
# NOTE in main.tf for what the full hardening requires.)
terraform apply -var-file=terraform.tfvars.local
```

> **Note on re-applies**: subsequent bootstrap applies are safe and idempotent. If you
> bootstrapped this account before the role-assignment change shipped, re-running
> `terraform apply` will add the role assignment. Wait ~30 seconds after apply for
> AAD role propagation before running `terraform init` in `infra/envs/prod/`.

After apply succeeds, capture three values from `terraform output`:

```bash
terraform output -raw storage_account_name   # e.g. jobragtfstateab123
terraform output -raw container_name         # always "tfstate"
terraform output -raw resource_group_name    # always "jobrag-tfstate-rg"
```

## Step 3 — Capture outputs into `envs/{prod,dev}/backend.tf`

Plan 04 writes `infra/envs/prod/backend.tf` with three placeholder literals; plan 06 writes the dev sibling. Update both AFTER bootstrap apply by replacing placeholders with the values from Step 2.

Example for `infra/envs/prod/backend.tf`:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "jobrag-tfstate-rg"           # from output
    storage_account_name = "jobragtfstateab123"          # from output (your suffix differs)
    container_name       = "tfstate"                      # from output
    key                  = "prod.tfstate"
    use_azuread_auth     = true
  }
}
```

Dev sibling (`infra/envs/dev/backend.tf`) uses the same three values but `key = "dev.tfstate"`.

## Step 4 — `terraform import` the External tenant (per D-05)

`azuread ~> 3.x` has no resource that creates a tenant, so we treat the manually-created tenant as the import target. There is no resource to import the tenant itself; the bootstrap's `azuread.external` provider alias is sufficient because the External tenant is consumed by `infra/envs/prod/identity.tf` (Plan 04+06) which references `var.tenant_id_external`.

This means **the "import" is implicit** — the tenant ID is captured as a Terraform variable and consumed downstream. No `terraform import` command is needed at this stage. (If a future Phase 8 portfolio refactor adopts the `azuread_directory_role_template` resource for tenant-level role checks, Plan 02-rev should add the import command here.)

## Step 5 — Bootstrap a first-login customer/Member account (~3 min)

Once the tenant exists (Step 1) and the storage backend is provisioned (Step 2),
create a customer/Member account that can actually sign in via the CIAM user
flow. **Do NOT skip this in favor of inviting a B2B guest** — see the warning
below.

### Why this isn't optional (B2B guest vs customer namespace)

Entra External ID has two disjoint identity namespaces inside the same tenant:

- **Customer/Member accounts** (this step) — created via `az ad user create` or
  the External-tenant self-service signup flow. These are the ONLY identities
  the CIAM user flow resolves at sign-in.
- **B2B guests** — created via the Entra-portal "Invite external user" flow
  (or auto-created when a workforce identity first signs into the External
  tenant). UPN has the form `<email>#EXT#@<tenant>.onmicrosoft.com`. They
  show up in `az ad user list`, but the CIAM user flow rejects them with
  "We couldn't find an account with this email address or password" because
  B2B guests authenticate against their **home tenant** via federation IdPs,
  which are NOT configured in v1.

Phase 4's first sign-in attempt cost ~1h diagnosing this exact trap (see
`.planning/phases/04-frontend-shell-auth/04-06-SUMMARY.md` deviation #6 and
`.planning/phases/04-frontend-shell-auth/04-06-RUNBOOK.md` Checkpoint 5).
Configuring federation IdPs to accept B2B guests is a future Phase-4-revision
path; the simpler v1 fix is to create a Member account directly in the
External tenant.

### Create the Member account

You must be `az login`'d to the **External tenant** for this step. Switch
context if you bootstrapped earlier in the workforce tenant:

```bash
# Confirm which tenant az is currently pointed at.
az account show --query tenantId -o tsv

# If it's NOT the External tenant ID from Step 1, switch:
az login --tenant <External-tenant-GUID-from-Step-1>
```

Then create the user (replace `adrian` and the password with your own — and
pick a strong throwaway, then rotate it on first sign-in):

```bash
# Single-line form (copy-pasteable, grep-friendly):
az ad user create --user-principal-name adrian@jobrag.onmicrosoft.com --display-name "Adrian Zaplata" --password '<strong-temp-password>' --force-change-password-next-sign-in false

# Multi-line equivalent (easier to read):
az ad user create \
  --user-principal-name adrian@jobrag.onmicrosoft.com \
  --display-name "Adrian Zaplata" \
  --password '<strong-temp-password>' \
  --force-change-password-next-sign-in false
```

Capture the resulting object ID (this is the `oid` claim that Phase 4's
AUTH-06 allowlist gate matches against):

```bash
az ad user show \
  --id adrian@jobrag.onmicrosoft.com \
  --query id -o tsv
# → e.g. 18d774c1-62ac-4416-8945-b5eca715e9ed
```

### Where this OID is used downstream

The captured OID feeds two places in the prod runbook:

1. **Key Vault secret** `seeded-user-entra-oid` — set via
   `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <oid>`.
   The ACA backend reads this via `secretRef` as the `SEEDED_USER_ENTRA_OID`
   env var; AUTH-06 rejects any JWT with a different `oid`.
2. **`users.entra_oid` row** — bridged from the seeded UUID to the real OID
   via `init_db()` on container boot (idempotent every-boot UPDATE — see
   Phase 04.1 fix 1 in `.planning/phases/04.1-phase-4-follow-ups-runbook-deviation-cleanup/04.1-01-SUMMARY.md`).
   After Phase 04.1 fix 1 lands, an ACA revision restart re-runs the bridge
   automatically — no more manual `az containerapp exec` UPDATE.

For the full first-sign-in walkthrough (KV set → ACA restart → live browser
sign-in → AUTH-04/07 verification), follow
`.planning/phases/04-frontend-shell-auth/04-06-RUNBOOK.md` Checkpoint 5.

### When to repeat this step

- **Fresh prod environment.** Every new External tenant + prod-env build pair.
- **Multi-user expansion (future).** Same `az ad user create` per user. AUTH-06
  needs to expand from single-OID equality to a `IN (...)` set or a role check
  (out of scope for v1).
- **OID rotation.** If the Member account is deleted + recreated, OID changes
  — re-run the KV `secret set` + restart ACA so `init_db()` re-bridges.

## Knowingly-accepted security trade-offs

- **Local state for bootstrap.** The state file `infra/bootstrap/terraform.tfstate` lives on Adrian's machine. It is gitignored. The blast-radius if leaked: the storage account name + RG name (no secrets, no app credentials). Acceptable trade — alternatives (in-Azure pre-provisioned state) defeat the chicken-and-egg solution.
- **Storage account is LRS, not GRS.** Cheaper, single-region durability. The state is recoverable from versioning + soft-delete; full DR is out of scope for v1.
- **Public network access is permitted on the storage account.** State backend access is RBAC-gated (`use_azuread_auth = true`); private endpoint would cost ~€10/mo for marginal value at this scope.
