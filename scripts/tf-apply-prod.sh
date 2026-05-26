#!/bin/bash
# Phase 06.1 D-07 — Canonical wrapper for `terraform <subcommand>` against infra/envs/prod/.
# Hard-codes the dual var-file invocation: prod.tfvars (committed) + prod.tfvars.local (gitignored).
#
# Why:
#   Running `terraform apply -var-file=prod.tfvars` ALONE leaves backend_audience /
#   entra_tenant_id / entra_tenant_subdomain at their "" defaults — which wipes the ACA
#   container's BACKEND_AUDIENCE / ENTRA_TENANT_* env vars and silently breaks Entra
#   auth. (Phase 06 UAT Bug #3, 06-UAT-DEBUG-HANDOFF.md.) The wrapper makes that
#   failure mode impossible by always passing both files.
#
# Usage (from repo root or anywhere — wrapper cd's into infra/envs/prod itself):
#   bash scripts/tf-apply-prod.sh plan
#   bash scripts/tf-apply-prod.sh apply
#   bash scripts/tf-apply-prod.sh apply -auto-approve
#   bash scripts/tf-apply-prod.sh apply -target=module.compute
#   bash scripts/tf-apply-prod.sh destroy
#   bash scripts/tf-apply-prod.sh plan -detailed-exitcode  # Plan 04 verification
#
# Optional escape hatch (testing the failure mode, e.g. confirming a CI apply ALSO
# wipes auth env when prod.tfvars.local is absent):
#   bash scripts/tf-apply-prod.sh --no-local plan
#
# Exit codes:
#   0  — terraform command succeeded
#   1  — terraform command failed (passthrough)
#   2  — prod.tfvars.local missing (and --no-local not set)
#   3  — no subcommand supplied
#   *  — passthrough from terraform (e.g. -detailed-exitcode returns 0/1/2)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROD_DIR="$REPO_ROOT/infra/envs/prod"
LOCAL_TFVARS="$PROD_DIR/prod.tfvars.local"

NO_LOCAL=0
if [ "${1:-}" = "--no-local" ]; then
  NO_LOCAL=1
  shift
fi

if [ "$#" -lt 1 ]; then
  echo "ERROR: no subcommand supplied" >&2
  echo "Usage: bash scripts/tf-apply-prod.sh <plan|apply|destroy|...> [terraform args]" >&2
  exit 3
fi

if [ "$NO_LOCAL" -eq 0 ] && [ ! -f "$LOCAL_TFVARS" ]; then
  echo "ERROR: Missing infra/envs/prod/prod.tfvars.local" >&2
  echo "" >&2
  echo "prod.tfvars.local carries the values that MUST be set on the ACA container" >&2
  echo "for Entra auth to work (backend_audience, entra_tenant_id, entra_tenant_subdomain,"  >&2
  echo "home_ip, api_audience). It is gitignored per .gitignore line 35." >&2
  echo "" >&2
  echo "Remediation: see infra/envs/prod/README.md 'Apply command convention' for the" >&2
  echo "file contents, or rebuild from infra/external/ outputs via" >&2
  echo "scripts/refresh-external-outputs.sh." >&2
  echo "" >&2
  echo "To bypass this check intentionally (e.g. for testing the failure mode):" >&2
  echo "  bash scripts/tf-apply-prod.sh --no-local <subcommand>" >&2
  exit 2
fi

cd "$PROD_DIR"

SUBCOMMAND="$1"
shift

if [ "$NO_LOCAL" -eq 1 ]; then
  exec terraform "$SUBCOMMAND" -var-file=prod.tfvars "$@"
else
  exec terraform "$SUBCOMMAND" -var-file=prod.tfvars -var-file=prod.tfvars.local "$@"
fi
