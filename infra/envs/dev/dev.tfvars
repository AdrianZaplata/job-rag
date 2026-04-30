# Dev environment — SCAFFOLD ONLY (CONTEXT.md D-04). Never applied in v1.
# Values here exist solely so `terraform plan -var-file=dev.tfvars` is a sanity check.

location = "westeurope"

# External tenant — same as prod (D-06 — single tenant for both)
tenant_id_external = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
tenant_subdomain   = "jobrag"

github_owner = "adrianzaplata"
github_repo  = "job-rag"

swa_origin = ""

# Placeholder home IP — never reaches a real Postgres firewall (dev never applies).
home_ip = "0.0.0.0"

ghcr_username = "adrianzaplata"
image_tag     = "latest"

budget_alert_email = "adrianzaplata@gmail.com"

seeded_user_id        = "REPLACE_WITH_ADRIAN_UUID"
seeded_user_entra_oid = "00000000-0000-0000-0000-000000000000"

# Application secrets — placeholders; dev never applies so these never reach KV.
# openai_api_key      = "dev-placeholder"
# langfuse_public_key = ""
# langfuse_secret_key = ""
