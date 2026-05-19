# Adrian's prod environment values.
# tfvars files are committed (no secrets in literal form — secrets come from terraform.tfvars.local
# or `-var` CLI flags or environment TF_VAR_*).

# Region
location = "westeurope"

# External tenant — replace tenant_id_external with bootstrap output value
tenant_id_external = "3fd51a76-f36e-43a1-aa37-564dad4c41fd"
tenant_subdomain   = "jobrag"

# GitHub — case-sensitive (Aug 2024 OIDC change: AADSTS7002138 if mismatched).
# Adrian's GitHub login is "AdrianZaplata"; the repo is "job-rag" (already lower).
github_owner = "AdrianZaplata"
github_repo  = "job-rag"

# CORS — DEPL-12 two-pass.
# First apply: leave empty → ALLOWED_ORIGINS = "http://localhost:5173".
# Second apply (after scripts/refresh-swa-origin.sh): script rewrites to "https://<swa-default>".
swa_origin = "https://witty-flower-065dac003.7.azurestaticapps.net"

# Postgres firewall — Adrian's home IP lives in terraform.tfvars.local (gitignored)
# to keep ISP/geolocation OPSEC data out of the public commit history. Variable has
# no default, so `terraform apply` fails loudly if absent. Refresh runbook lives in
# modules/database/README.md and mutates terraform.tfvars.local.

# GHCR
ghcr_username = "adrianzaplata"
# ghcr_pat — DO NOT commit; provide via TF_VAR_ghcr_pat or terraform.tfvars.local
image_tag = "latest"

# Budget
budget_alert_email = "adrianzaplata@gmail.com"

# Bootstrap state container — same values as backend.tf. Used to grant the GHA SP
# Storage Blob Data Contributor on the tfstate container so deploy-infra.yml works.
tfstate_storage_account_name = "jobragtfstateq7u9r"
tfstate_resource_group_name  = "jobrag-tfstate-rg"
tfstate_container_name       = "tfstate"

# Application IDs
seeded_user_id        = "00000000-0000-0000-0000-000000000001" # Phase 1 D-08 SEEDED_USER_ID
seeded_user_entra_oid = "00000000-0000-0000-0000-000000000000" # Phase 4 fills after first login

# Human deployer (Adrian) user OID for KV Secrets Officer assignment.
# Stable across local apply + CI plan contexts (Gap H fix).
deployer_object_id = "58ad20b2-0cba-4d5b-81cd-84d29f64daa2"

# Application secrets are SEEDED OUT-OF-BAND directly in Key Vault (Option B).
# After first apply, run (once per environment + on rotation):
#   az keyvault secret set --vault-name <kv-name> --name openai-api-key      --value "<sk-...>"
#   az keyvault secret set --vault-name <kv-name> --name langfuse-public-key --value "<pk-...>"
#   az keyvault secret set --vault-name <kv-name> --name langfuse-secret-key --value "<sk-...>"
# See README "Out-of-band secret seeding". Subsequent `terraform apply` runs will NOT
# overwrite these (lifecycle.ignore_changes = [value] on the *_key_vault_secret resources).
