---
phase: 03-infrastructure-ci-cd
reviewed: 2026-05-19T12:00:00Z
depth: standard
files_reviewed: 41
files_reviewed_list:
  - .gitattributes
  - .gitignore
  - .github/workflows/bootstrap-corpus.yml
  - .github/workflows/ci.yml
  - .github/workflows/deploy-api.yml
  - .github/workflows/deploy-infra.yml
  - .github/workflows/deploy-spa.yml
  - .github/workflows/static-tf.yml
  - Dockerfile
  - alembic/env.py
  - infra/.tflint.hcl
  - infra/.tfsec/config.yml
  - infra/bootstrap/identity.tf
  - infra/bootstrap/main.tf
  - infra/bootstrap/outputs.tf
  - infra/envs/dev/backend.tf
  - infra/envs/dev/dev.tfvars
  - infra/envs/dev/locals.tf
  - infra/envs/dev/main.tf
  - infra/envs/dev/outputs.tf
  - infra/envs/dev/provider.tf
  - infra/envs/dev/variables.tf
  - infra/envs/prod/backend.tf
  - infra/envs/prod/locals.tf
  - infra/envs/prod/main.tf
  - infra/envs/prod/outputs.tf
  - infra/envs/prod/prod.tfvars
  - infra/envs/prod/provider.tf
  - infra/envs/prod/variables.tf
  - infra/modules/compute/main.tf
  - infra/modules/compute/outputs.tf
  - infra/modules/compute/variables.tf
  - infra/modules/database/main.tf
  - infra/modules/database/outputs.tf
  - infra/modules/database/variables.tf
  - infra/modules/identity/main.tf
  - infra/modules/identity/outputs.tf
  - infra/modules/identity/variables.tf
  - infra/modules/kv/main.tf
  - infra/modules/kv/outputs.tf
  - infra/modules/kv/variables.tf
  - infra/modules/monitoring/main.tf
  - infra/modules/monitoring/outputs.tf
  - infra/modules/monitoring/variables.tf
  - infra/modules/network/main.tf
  - infra/modules/network/outputs.tf
  - infra/modules/network/variables.tf
  - scripts/docker-entrypoint.sh
  - scripts/refresh-swa-origin.sh
  - src/job_rag/__init__.py
  - src/job_rag/config.py
  - src/job_rag/db/engine.py
  - src/job_rag/services/ingestion.py
  - tests/test_alembic.py
  - tests/test_api.py
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-19T12:00:00Z
**Depth:** standard
**Files Reviewed:** 41 source files (Terraform, GitHub Actions YAML, shell scripts, Python touches)
**Status:** issues_found (advisory — none block phase completion)

## Summary

Phase 3 is a substantial cloud / IaC delivery: 7 Terraform modules, 2 env compositions, 1 bootstrap surface, 5 GitHub Actions workflows, 2 shell scripts, and ~5 minor Python touches. Overall posture is strong:

- **OIDC discipline:** No long-lived Azure credentials in GitHub secrets. Federated identity correctly scoped per subject (`master` push vs `environment:production`). Workforce/External tenant split is explicit and rationalized (Gap D).
- **Secrets handling:** Production KV secrets migrated from plain `value` to `value_wo` + `value_wo_version` (Gap 16.A) so values never persist in TF state. Out-of-band seeding for OpenAI/Langfuse keeps them off GitHub entirely. Postgres admin password is random 32-char alphanumeric written via `value_wo`.
- **RBAC posture:** All role assignments are narrowly scoped (KV-scoped, RG-scoped, container-scoped on tfstate). The two subscription-scope grants (Cost Management Contributor, Reader) are documented D-08 exceptions with explicit mutation-isolation rationale.
- **Audit trail:** KV `AuditEvent` and ACA `ContainerAppConsoleLogs` flow into Log Analytics (Gap 10.A), with documented trade-off on `ContainerAppSystemLogs` (Gap 12.B / D-16).
- **Defensive bootstrap:** State storage uses AAD-auth (`use_azuread_auth=true`), TLS 1.2 floor, soft-delete + versioning. Bootstrap state is local and gitignored.

The findings below are all non-blocking. The four warnings cluster around dev/prod mirror drift, an exposed-but-rotatable residential IP, and one shell-script cleanup gap. The info items are style/cleanup nits.

## Warnings

### WR-01: Dev composition uses incorrect diagnostic category name (would fail on apply)

**File:** `infra/envs/dev/main.tf:196`
**Issue:** The dev composition writes `category = "ContainerAppConsoleLogs_CL"` (with the `_CL` suffix). The prod composition's own inline comment (lines 227-228) explicitly calls this out as wrong: "The `_CL` suffix is the LAW *table name* — diagnostic category names drop it." Prod uses the correct `category = "ContainerAppConsoleLogs"` (line 236). Dev is gated by D-04 ("never applied in v1"), so this has not been caught by an actual `terraform apply`. If/when dev is applied, it will 400 with `"Category 'ContainerAppConsoleLogs_CL' is not supported"`.
**Fix:**
```hcl
# infra/envs/dev/main.tf:196
enabled_log {
  category = "ContainerAppConsoleLogs"   # drop _CL suffix; that suffix is the LAW table name, not the category
}
# NOTE: ContainerAppSystemLogs intentionally omitted per D-16.
```

### WR-02: Dev KV secrets store plaintext value (lags prod Gap 16.A migration)

**File:** `infra/envs/dev/main.tf:109-150`
**Issue:** Prod migrated all four `azurerm_key_vault_secret` resources from `value = ...` to `value_wo = ...` + `value_wo_version = 1` (commits `38f06eb` Gap 16.A) so secret values never land in TF state. Dev still uses the old `value = "managed-out-of-band"` form. The literal value here is a sentinel string, but the `seeded_user_entra_oid` block (line 147) reads `value = var.seeded_user_entra_oid` — if that variable ever holds a real OID, it persists in dev state. Same exposure profile prod had pre-Gap-16.A. Even with `lifecycle.ignore_changes = [value]`, the initial plaintext write hits state.
**Fix:** Mirror the prod pattern verbatim:
```hcl
# infra/envs/dev/main.tf:109-150 — apply to all four secret blocks
resource "azurerm_key_vault_secret" "openai_api_key" {
  name             = "openai-api-key"
  value_wo         = "managed-out-of-band"
  value_wo_version = 1
  key_vault_id     = module.kv.kv_id
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.deployer_kv_secrets_officer]
  lifecycle {
    ignore_changes = [value]
  }
}
# (repeat for langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid)
```

### WR-03: Real residential IP committed to public repo via prod.tfvars

**File:** `infra/envs/prod/prod.tfvars:23`
**Issue:** `home_ip = "79.228.31.2"` is a real residential IP committed to a public repo (project README confirms "public repo, script-driven, workforce SP" posture). The Postgres firewall rule is gated by TLS + a 32-char random password (defence-in-depth holds even if the IP rotates to a different ISP customer), but the value still leaks Adrian's home network ISP-allocated IP, which is a non-trivial OPSEC datapoint (geolocation, ISP, residential-vs-commercial). The refresh runbook in `infra/modules/database/README.md:48` mutates this file in place with `sed`, ensuring every IP rotation gets committed too.
**Fix:** Two options, pick whichever fits the workflow:
1. **Move `home_ip` out of the committed tfvars:** declare in `terraform.tfvars.local` (already in `.gitignore`) and remove the literal from `prod.tfvars`. Variable already has no default — TF will fail loudly if absent. Update the runbook to mutate the local file.
2. **Accept the trade-off explicitly:** add a comment to `prod.tfvars` referencing the threat decision and acknowledging the IP is rotatable and not load-bearing for auth.

The README in `infra/modules/database/` already documents the refresh cadence — the choice is whether the IP itself belongs in the public commit history or a local-only file.

### WR-04: `refresh-swa-origin.sh` leaves a `.bak` file in the env directory

**File:** `scripts/refresh-swa-origin.sh:21`
**Issue:** `sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars` creates `prod.tfvars.bak` in `infra/envs/prod/`. The script never removes the backup, and `.tfvars` is not in `.gitignore` so the `.bak` file is visible to `git status` after every run. Low-risk (the contents are identical to the pre-edit tfvars file already in the repo), but a literal hand-edit slip-up could end up committing it. Also, the script does not validate that `terraform output -raw swa_default_origin` returned a non-empty value before string-templating.
**Fix:**
```bash
# scripts/refresh-swa-origin.sh
set -euo pipefail
cd "$(dirname "$0")/../infra/envs/prod"

SWA_HOST="$(terraform output -raw swa_default_origin)"
if [ -z "$SWA_HOST" ]; then
  echo "FATAL: terraform output swa_default_origin returned empty" >&2
  exit 1
fi
SWA_ORIGIN="https://${SWA_HOST}"

if grep -q '^swa_origin' prod.tfvars; then
  sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars
  rm -f prod.tfvars.bak       # cleanup; macOS sed leaves a .bak we don't need
else
  echo "swa_origin = \"$SWA_ORIGIN\"" >> prod.tfvars
fi

terraform apply -var-file=prod.tfvars -auto-approve
```

Alternative: also add `*.bak` to the repo's `.gitignore` as a belt-and-suspenders.

## Info

### IN-01: Sentinel deploy-trigger comment left in `__init__.py`

**File:** `src/job_rag/__init__.py:1`
**Issue:** The file contains a single line: `# trigger deploy-api after GHCR bootstrap`. This was a deliberate touch to retrigger `deploy-api.yml` after GHCR was bootstrapped (commits `ea0af2d`, `5195efc`). It's no longer load-bearing.
**Fix:** Delete the comment so the file is empty (a valid empty `__init__.py` is sufficient for the package). Or replace with a meaningful docstring describing the package.

### IN-02: `aca_kv_secrets_user` role assignment missing `description`

**File:** `infra/envs/prod/main.tf:214-218`
**Issue:** Three other `azurerm_role_assignment` blocks in this file (`gha_tfstate_blob_data_contributor` line 48, `deployer_kv_secrets_officer` line 104) have `description` fields explaining the assignment rationale. `aca_kv_secrets_user` does not. Inconsistent audit trail.
**Fix:**
```hcl
resource "azurerm_role_assignment" "aca_kv_secrets_user" {
  scope                = module.kv.kv_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = module.compute.aca_principal_id
  description          = "Grants the ACA system-assigned MI read access to KV secret values at container start (D-13)."
}
```

### IN-03: Redundant ternary in `allowed_origins_csv`

**File:** `infra/envs/prod/locals.tf:15` and `infra/envs/dev/locals.tf:14`
**Issue:** `var.swa_origin == "" ? "" : var.swa_origin` evaluates to `var.swa_origin` in both branches. The `compact()` call already strips empty strings.
**Fix:**
```hcl
allowed_origins_csv = join(",", compact([
  var.swa_origin,
  "http://localhost:5173",
]))
```

### IN-04: Redundant file-exists guards in `static-tf.yml`

**File:** `.github/workflows/static-tf.yml:50, 56, 62`
**Issue:** `if [ -f infra/envs/prod/main.tf ]; then ...; fi` — the file is checked into the repo; the conditional always evaluates true. Adds noise without protection.
**Fix:** Drop the conditional; let the `terraform init` step fail naturally if a `main.tf` ever disappears.

### IN-05: Fragile cost-string round-trip in `ingest_directory`

**File:** `src/job_rag/services/ingestion.py:450-452`
**Issue:** `ingest_file` produces `f"ingested (${result.total_cost_usd:.4f})"`, then `ingest_directory` parses it back out with `reason.split("$")[1].rstrip(")")`. The float is already known at the producer; the round-trip via formatted string + regex-ish parsing is fragile if the reason format ever changes (e.g., adding a locale, currency, or status). No bug today, but a code smell.
**Fix:** Change `ingest_file` to also return cost (4-tuple) or have `ingest_directory` open its own async path:
```python
# Option A: 4-tuple return (breaks signature parity — touches CLI + /ingest)
return True, "ingested", posting_id, result.total_cost_usd

# Option B: ingest_directory builds its own MarkdownFileSource per file and
# calls ingest_from_source directly, keeping the typed IngestResult in scope.
```
Deferrable — the current behavior is correct.

### IN-06: Python URL-encoder spawn in container entrypoint

**File:** `scripts/docker-entrypoint.sh:14`
**Issue:** Spawns `python3 -c "..."` to URL-encode the postgres password at every container start. The comment correctly notes the password is alphanumeric per D-11 so encoding is a no-op. Adds ~50-100ms launch overhead and a process fork for no functional gain. Defensive against future password-policy changes, but if/when that changes, the right place is the password generator (`infra/modules/database/main.tf:19`).
**Fix:** Either drop the encoding (inline `ENCODED_PWD="$POSTGRES_ADMIN_PASSWORD"` with a comment referencing D-11) or move it server-side into `src/job_rag/config.py:_compose_db_urls_from_parts` which already does this correctly via `urllib.parse.quote(password, safe="")`. The Python-side composition already exists; the shell-side composition is largely redundant once `Settings._compose_db_urls_from_parts` runs.

### IN-07: `cost_management_contributor` + `reader_subscription` widen blast radius

**File:** `infra/modules/identity/main.tf:108-129`
**Issue:** The GHA SP is granted: `Contributor` at `prod-rg` (line 83), `Cost Management Contributor` at subscription (line 108), and `Reader` at subscription (line 124). Both subscription-scope grants are documented (D-08 v2 Amendment, Gap 8.D, Gaps F+G), and Reader is `*/read` only. Still, the combination broadens what a compromised CI run can enumerate (every resource in the subscription) and bills (consumption budgets across the subscription). The "named exception" framing in the comments is correct, but a future reviewer should know this is a deliberate widening of D-08's "RG-scoped only" rule.
**Fix:** No code change recommended; the existing comments already capture the rationale. Flag this for the user's audit log so a future reader doesn't re-relitigate D-08 from cold. Optionally, add a `# AUDIT-D-08` tag-style comment at both resources so `grep -rn AUDIT-D-08 infra/` returns the full set of documented exceptions in one shot.

---

## Notes (out of v1 scope, no findings raised)

- **Public Postgres firewall (0.0.0.0):** `infra/modules/database/main.tf:103-107` adds the "Allow Azure services" rule. Documented in `tfsec/config.yml` as a knowingly-accepted trade-off (D-10 / A1 Path A, €130/mo private-endpoint cost vs. TLS + 32-char password as the boundary). Reviewer agrees with the documented framing.
- **Single-replica `max_replicas = 1`:** documented single-user v1 constraint, not a code smell.
- **`timestamp()` in budget `start_date`:** `infra/modules/monitoring/main.tf:62` uses non-deterministic `timestamp()` but mitigated by `lifecycle.ignore_changes = [time_period[0].start_date]`. Behaves correctly across re-plans.
- **GHA SP cannot manage External tenant:** documented in `infra/modules/identity/main.tf:20-38` as Gap D. CIAM trust boundary is preserved.
- **Tests `test_0004_*_smoke` mutate global DB state:** standard pattern for Alembic migration tests; tests downgrade + re-upgrade. Safe for serial CI; would clash under pytest-xdist.

---

_Reviewed: 2026-05-19T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
