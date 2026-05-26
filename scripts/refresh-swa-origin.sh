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

# Read SWA default host name from terraform state (must come from a TF output).
# Validate the output is non-empty before string-templating — otherwise we'd
# silently write `swa_origin = "https://"` and pass a broken value to apply.
SWA_HOST="$(terraform output -raw swa_default_origin)"
if [ -z "$SWA_HOST" ]; then
  echo "FATAL: terraform output swa_default_origin returned empty" >&2
  exit 1
fi
SWA_ORIGIN="https://${SWA_HOST}"

# Phase 06.1 D-07 — pass 2 (CORS refresh) MUST also load prod.tfvars.local, or it
# silently re-wipes BACKEND_AUDIENCE / ENTRA_TENANT_* env vars (Bug #3). Guard
# BEFORE the sed rewrite so we never leave prod.tfvars half-mutated to a stale
# SWA origin with no apply to settle it (WR-02).
if [ ! -f prod.tfvars.local ]; then
  echo "FATAL: prod.tfvars.local missing — see infra/envs/prod/README.md 'Apply command convention'" >&2
  exit 2
fi

# Re-write prod.tfvars in place
if grep -q '^swa_origin' prod.tfvars; then
  sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars
  rm -f prod.tfvars.bak # cleanup; macOS sed leaves a .bak we don't need
else
  echo "swa_origin = \"$SWA_ORIGIN\"" >> prod.tfvars
fi

terraform apply -var-file=prod.tfvars -var-file=prod.tfvars.local -auto-approve
