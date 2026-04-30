#!/bin/bash
set -euo pipefail

# Phase 3 ACA composition: when POSTGRES_HOST is set (ACA env vars from compute
# module) AND DATABASE_URL is not pre-composed, build it from the parts.
# Local docker-compose sets DATABASE_URL pre-composed so this branch is a no-op there.
if [[ -n "${POSTGRES_HOST:-}" && -z "${DATABASE_URL:-}" ]]; then
  : "${POSTGRES_USER:?POSTGRES_USER required when POSTGRES_HOST is set}"
  : "${POSTGRES_DB:?POSTGRES_DB required when POSTGRES_HOST is set}"
  : "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD required when POSTGRES_HOST is set}"

  # URL-encode the password (alphanumeric per D-11 — encoding is a no-op but
  # defensive in case of future password policy change).
  ENCODED_PWD="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$POSTGRES_ADMIN_PASSWORD")"

  export DATABASE_URL="postgresql://${POSTGRES_USER}:${ENCODED_PWD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
  export ASYNC_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${ENCODED_PWD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?ssl=require"

  echo "Composed DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* parts (ACA env)."
fi

echo "Running database migrations..."
job-rag init-db

echo "Starting API server..."
exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000
