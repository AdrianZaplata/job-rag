#!/usr/bin/env bash
# Phase 4 D-02 helper — read infra/external/ outputs and paste into
# downstream gitignored files. Mirrors scripts/refresh-swa-origin.sh idiom.
# Run after every infra/external/ apply.
set -euo pipefail

cd "$(dirname "$0")/../infra/external"

SPA_CLIENT_ID="$(terraform output -raw spa_client_id 2>/dev/null || true)"
API_CLIENT_ID="$(terraform output -raw api_client_id 2>/dev/null || true)"
API_AUDIENCE_URI="$(terraform output -raw api_audience_uri 2>/dev/null || true)"
API_SCOPE_NAME="$(terraform output -raw api_scope_name 2>/dev/null || true)"

# Phase 04.1-06 — fail-loud guard against the documented silent-fail mode on
# azuread_application_identifier_uri (memory terraform-azuread-identifier-uri-unreliable.md).
# terraform output can return a stale or empty value if the underlying resource
# applied "successfully" but the live identifierUris list stayed empty. We assert
# live state directly via Microsoft Graph BEFORE rewriting any downstream files.
if [ -n "$API_CLIENT_ID" ]; then
  echo "Verifying live identifierUris for API app $API_CLIENT_ID ..."
  LIVE_URIS="$(az ad app show --id "$API_CLIENT_ID" --query 'identifierUris' -o tsv 2>/dev/null || true)"
  if [ -z "$LIVE_URIS" ]; then
    echo "FATAL: az ad app show returned empty identifierUris for $API_CLIENT_ID" >&2
    echo "       The terraform output says api_audience_uri=$API_AUDIENCE_URI but the live" >&2
    echo "       Entra app has NO identifierUris set. This is the documented silent-fail" >&2
    echo "       mode on azuread_application_identifier_uri (see memory" >&2
    echo "       terraform-azuread-identifier-uri-unreliable.md). Aborting BEFORE downstream" >&2
    echo "       files (frontend/.env.production, prod.tfvars.local, GitHub secrets) are" >&2
    echo "       rewritten with stale/empty values. Unblock with:" >&2
    echo "         az ad app update --id $API_CLIENT_ID --identifier-uris \"$API_AUDIENCE_URI\"" >&2
    echo "       then re-run: bash scripts/refresh-external-outputs.sh" >&2
    exit 2
  fi
  echo "✓ Live identifierUris=$LIVE_URIS (matches expected $API_AUDIENCE_URI)"
fi

if [ -z "$SPA_CLIENT_ID" ] || [ -z "$API_AUDIENCE_URI" ]; then
  echo "FATAL: terraform output missing — apply infra/external/ first" >&2
  exit 1
fi

PROD_TFVARS="../envs/prod/prod.tfvars.local"
if [ -f "$PROD_TFVARS" ]; then
  # Replace or append api_audience and backend_audience lines.
  for key in api_audience backend_audience; do
    if grep -q "^${key}" "$PROD_TFVARS"; then
      sed -i.bak "s|^${key}.*|${key} = \"${API_AUDIENCE_URI}\"|" "$PROD_TFVARS"
      rm -f "${PROD_TFVARS}.bak"
    else
      echo "${key} = \"${API_AUDIENCE_URI}\"" >> "$PROD_TFVARS"
    fi
  done
  echo "✓ Updated $PROD_TFVARS with api_audience + backend_audience"
else
  echo "⚠ $PROD_TFVARS does not exist — create it from infra/envs/prod/prod.tfvars (gitignored .local pattern)" >&2
fi

FRONTEND_ENV="../../frontend/.env.production"
if [ -f "$FRONTEND_ENV" ]; then
  for kvpair in "VITE_SPA_CLIENT_ID=${SPA_CLIENT_ID}" "VITE_API_AUDIENCE=${API_AUDIENCE_URI}"; do
    key="${kvpair%%=*}"
    if grep -q "^${key}=" "$FRONTEND_ENV"; then
      sed -i.bak "s|^${key}=.*|${kvpair}|" "$FRONTEND_ENV"
      rm -f "${FRONTEND_ENV}.bak"
    else
      echo "${kvpair}" >> "$FRONTEND_ENV"
    fi
  done
  echo "✓ Updated $FRONTEND_ENV with VITE_SPA_CLIENT_ID + VITE_API_AUDIENCE"
else
  echo "⚠ $FRONTEND_ENV does not exist yet — Plan 04 creates it" >&2
fi

echo ""
echo "Outputs (copy to GitHub secrets if needed):"
echo "  SPA_CLIENT_ID:   $SPA_CLIENT_ID"
echo "  API_CLIENT_ID:   $API_CLIENT_ID"
echo "  API_AUDIENCE:    $API_AUDIENCE_URI"
echo "  API_SCOPE:       $API_SCOPE_NAME"
echo ""
echo "GitHub secret set commands:"
echo "  gh secret set VITE_SPA_CLIENT_ID --body '${SPA_CLIENT_ID}'"
echo "  gh secret set VITE_API_AUDIENCE  --body '${API_AUDIENCE_URI}'"
