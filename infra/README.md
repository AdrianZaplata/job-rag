# Infrastructure

> Phase 3 of the job-rag milestone: provision the Azure stack (Container Apps, Postgres Flex B1ms with pgvector, Static Web Apps Free, Key Vault, Log Analytics) plus three OIDC-federated GitHub Actions workflows. Everything is Terraform-managed; portal edits will drift on next `apply`.

---

## Layout

| Directory | Purpose | State |
|-----------|---------|-------|
| `bootstrap/` | One-time: creates the Azure Blob storage account that hosts state for `envs/`. | LOCAL `.tfstate` (gitignored). |
| `modules/` | Shared module library: `network`, `database`, `compute`, `identity`, `monitoring`, `kv`. | n/a (modules don't hold state). |
| `envs/prod/` | Active prod environment composition. | Remote `prod.tfstate` in Azure Blob. |
| `envs/dev/` | Scaffold-only — never `apply`d in v1 (D-04). | Remote `dev.tfstate` in Azure Blob. |

## Bootstrap → first apply runbook

1. `cd infra/bootstrap && terraform init && terraform apply` (one-time, manual)
2. Copy outputs into `infra/envs/prod/backend.tf` literals
3. `cd infra/envs/prod && terraform init && terraform apply -var-file=prod.tfvars` (first pass — `swa_origin` empty)
4. `bash scripts/refresh-swa-origin.sh` (reads SWA default origin, rewrites tfvars, re-applies — second pass)
5. Verify with the post-apply smoke checklist in `envs/prod/README.md`

See per-directory READMEs for full instructions.

## Validation

Static checks (`fmt`, `validate`, `tflint`, `tfsec`) run in CI via `.github/workflows/static-tf.yml` on every PR touching `infra/**`.

Live-Azure smoke runs once at phase close per `envs/prod/README.md` post-apply checklist.
