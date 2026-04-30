# Adrian's prod environment values.
# tfvars files are committed (no secrets in literal form — secrets come from terraform.tfvars.local
# or `-var` CLI flags or environment TF_VAR_*).

# Region
location = "westeurope"

# External tenant — replace tenant_id_external with bootstrap output value
tenant_id_external = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
tenant_subdomain   = "jobrag"

# GitHub
github_owner = "adrianzaplata"
github_repo  = "job-rag"

# CORS — DEPL-12 two-pass.
# First apply: leave empty → ALLOWED_ORIGINS = "http://localhost:5173".
# Second apply (after scripts/refresh-swa-origin.sh): script rewrites to "https://<swa-default>".
swa_origin = ""

# Postgres firewall — Adrian's home IP (refresh via runbook in modules/database/README.md)
home_ip = "REPLACE_WITH_CURRENT_HOME_IP"

# GHCR
ghcr_username = "adrianzaplata"
# ghcr_pat — DO NOT commit; provide via TF_VAR_ghcr_pat or terraform.tfvars.local
image_tag = "latest"

# Budget
budget_alert_email = "adrianzaplata@gmail.com"

# Application IDs
seeded_user_id        = "REPLACE_WITH_ADRIAN_UUID"             # Phase 1 D-08 SEEDED_USER_ID
seeded_user_entra_oid = "00000000-0000-0000-0000-000000000000" # Phase 4 fills after first login

# Application secrets — DO NOT commit; provide via terraform.tfvars.local or TF_VAR_*
# openai_api_key       = "..."
# langfuse_public_key  = "..."
# langfuse_secret_key  = "..."
