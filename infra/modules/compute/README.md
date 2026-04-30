# Module: compute (Container App)

Single resource: `azurerm_container_app`. Largest single TF surface in Phase 3.

## AVM decision (D-03)

**Use raw `azurerm`.** AVM `Azure/avm-res-app/container-app/azurerm` is still pre-stable as of April 2026 (RESEARCH.md §AVM Adoption). The raw resource has stabilized and Microsoft samples + Pattern 4 from RESEARCH.md provide a battle-tested skeleton.

## Key behaviors

- **Scale-to-zero** (D-17): `min_replicas = 0`, `max_replicas = 1`. Cold-start mitigation defers to Phase 6 (UX state).
- **Graceful shutdown** (D-15): `termination_grace_period_seconds = 120`. Pairs with Phase 1's app-level 30s drain + 60s agent timeout (D-25).
- **System-assigned MI** (D-13): the Container App owns its identity lifecycle. The KV `Secrets User` role assignment is wired by the composition layer (`envs/prod/main.tf`) AFTER both modules apply.
- **5 KV-backed secrets** (D-13): consumed via `key_vault_secret_id` URI references — values NEVER enter TF state. Resolved at container start.
- **1 literal secret** (`ghcr-pat`): chicken-and-egg with KV — Container App must pull image before MI can resolve KV refs. Marked `sensitive = true`; PAT is fine-grained read-only on the package only.

## Image lifecycle ownership (B5 fix)

After the first `deploy-api.yml` run (which builds + pushes a SHA-pinned image and runs `az containerapp update --image ghcr.io/.../job-rag:${{ github.sha }}`), the live Container App revision references a SHA, not `:latest`. A subsequent `terraform apply` (for example, the second-pass CORS apply) WOULD revert the image back to whatever `var.image_tag` resolves to (default `"latest"`) — undoing the CI-driven deployment.

The fix: `lifecycle { ignore_changes = [template[0].container[0].image, template[0].revision_suffix] }` on `azurerm_container_app.api`. Terraform's view of the image will diverge from reality after first deploy-api.yml run, but that's the correct trade-off for a CI-driven image lifecycle:

- **Terraform owns:** Container App resource shape (replicas, ingress, env vars, secrets, MI).
- **deploy-api.yml owns:** the running image tag.

If the divergence ever becomes a problem (e.g. drift detection runs flag the image), use `terraform apply -refresh-only` to import the live state without reverting.

## Env var contract (matches Phase 1 Settings model)

| Env var | Source | Phase 1 ref |
|---------|--------|-------------|
| `OPENAI_API_KEY` | KV secret `openai-api-key` | settings.openai_api_key |
| `POSTGRES_ADMIN_PASSWORD` | KV secret `postgres-admin-password` | composed into DATABASE_URL by entrypoint |
| `POSTGRES_HOST` / `POSTGRES_DB` / `POSTGRES_USER` | literal env vars | composed into DATABASE_URL by entrypoint |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | KV secrets | settings.langfuse_*_key |
| `SEEDED_USER_ENTRA_OID` | KV secret (placeholder per D-09) | Phase 4 fills |
| `ALLOWED_ORIGINS` | literal CSV — second-apply rewrites per DEPL-12 | settings.allowed_origins (Phase 1 NoDecode pattern) |
| `SEEDED_USER_ID` | literal UUID | settings.seeded_user_id (Phase 1 D-08) |
| `AGENT_TIMEOUT_SECONDS` / `HEARTBEAT_INTERVAL_SECONDS` | literals | Phase 1 D-25 / BACK-05 |
| `JOB_RAG_API_KEY` | literal "" | disabled in prod (Phase 4 Entra JWT replaces) |

## Entrypoint composition

The Phase 1 `scripts/docker-entrypoint.sh` calls `job-rag init-db` which reads `DATABASE_URL` from env. Phase 3 emits POSTGRES_* parts; the entrypoint must compose:

```bash
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
export ASYNC_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?ssl=require"
```

Plan 05 documents whether this needs a Phase 3 entrypoint update (likely yes — Phase 1's entrypoint expected the env vars pre-composed by docker-compose).
