#!/bin/bash
# DEPL-12 / Plan-Locking Addendum A3: Two-Pass CORS Bootstrap helper.
# Reads the SWA default origin from terraform output, rewrites prod.tfvars,
# and re-runs `terraform apply -var-file=prod.tfvars`.
#
# Idempotent: safe to re-run. If `swa_origin` already matches the current
# SWA default host, the second `apply` is a no-op revision.
#
# This script is intentionally one-shot infra glue (per the user's reusable-
# tools default — not folded into the `job-rag` Typer CLI; reuse expected
# near-zero).

set -euo pipefail
cd "$(dirname "$0")/../infra/envs/prod"

# Read SWA default host name from terraform state (must come from a TF output)
SWA_ORIGIN="https://$(terraform output -raw swa_default_origin)"

# Re-write prod.tfvars in place
if grep -q '^swa_origin' prod.tfvars; then
  sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars
else
  echo "swa_origin = \"$SWA_ORIGIN\"" >> prod.tfvars
fi

terraform apply -var-file=prod.tfvars -auto-approve
