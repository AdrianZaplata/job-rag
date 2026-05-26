terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
  }
}

# Container App per CONTEXT.md D-03 — RAW azurerm (AVM is pre-stable for ACA).
# Per RESEARCH.md Pattern 4 — the canonical skeleton. Key decisions baked in:
# - System-assigned MI (D-13): owned by the Container App lifecycle.
# - Scale-to-zero: min_replicas=0, max_replicas=1 (DEPL-03, D-17).
# - termination_grace_period_seconds=120 (D-15) — Phase 1 D-17 + Envoy 240s ceiling.
# - revision_mode="Single" — simplest blue-green via traffic-split-on-deploy (Discretion).
# - 5 KV-backed secrets via key_vault_secret_id URI references (D-13) — values
#   never enter TF state.
# - 1 literal secret: GHCR PAT (chicken-and-egg with KV — image must pull before
#   container can start before MI can resolve KV). Marked sensitive=true; PAT is
#   fine-grained read-only on the package (RESEARCH.md Pitfall §ghcr-pat).
resource "azurerm_container_app" "api" {
  name                         = "jobrag-${var.env}-api"
  container_app_environment_id = var.aca_env_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-pat"
  }

  # Literal-value secret — read-only fine-grained PAT on the GHCR package.
  # Lives in TF state but marked sensitive (input variable also sensitive).
  secret {
    name  = "ghcr-pat"
    value = var.ghcr_pat
  }

  # KV-backed secrets — values never enter TF state. Container App's system MI
  # resolves them at container start; updates propagate via revision swap.
  # The keys of var.kv_secret_uris MUST match these names exactly.
  secret {
    name                = "openai-api-key"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["openai-api-key"]
  }
  secret {
    name                = "postgres-admin-password"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["postgres-admin-password"]
  }
  secret {
    name                = "langfuse-public-key"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["langfuse-public-key"]
  }
  secret {
    name                = "langfuse-secret-key"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["langfuse-secret-key"]
  }
  secret {
    name                = "seeded-user-entra-oid"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["seeded-user-entra-oid"]
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false # HTTPS-only

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # B5 fix: image_tag is owned by deploy-api.yml after first manual push.
  # terraform apply MUST NOT revert the SHA-pinned revision deployed by CI.
  # See README.md "Image lifecycle ownership" for the trade-off.
  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      template[0].revision_suffix,
    ]
    # WR-03: enforce the Azure Consumption profile's cpu:memory 1:2 ratio at
    # plan time. The per-variable `contains()` validation lists in
    # variables.tf check each value in isolation; this precondition catches
    # the cross-variable foot-gun (e.g., cpu=1.0 + memory="0.5Gi" would pass
    # both per-variable validators but fail with an opaque ContainerAppInvalid
    # 4xx from ARM at apply time).
    precondition {
      condition = (
        (var.cpu == 0.25 && var.memory == "0.5Gi") ||
        (var.cpu == 0.5 && var.memory == "1Gi") ||
        (var.cpu == 0.75 && var.memory == "1.5Gi") ||
        (var.cpu == 1.0 && var.memory == "2Gi") ||
        (var.cpu == 1.25 && var.memory == "2.5Gi") ||
        (var.cpu == 1.5 && var.memory == "3Gi") ||
        (var.cpu == 1.75 && var.memory == "3.5Gi") ||
        (var.cpu == 2.0 && var.memory == "4Gi")
      )
      error_message = "Azure Consumption profile requires cpu:memory 1:2 ratio. Got cpu=${var.cpu}, memory=${var.memory}. Valid pairs: 0.25/0.5Gi, 0.5/1Gi, 0.75/1.5Gi, 1.0/2Gi, 1.25/2.5Gi, 1.5/3Gi, 1.75/3.5Gi, 2.0/4Gi."
    }
  }

  template {
    min_replicas                     = 0   # scale-to-zero (D-17, DEPL-03)
    max_replicas                     = 1   # single-user
    termination_grace_period_seconds = 120 # D-15

    container {
      name   = "api"
      image  = "ghcr.io/${var.ghcr_username}/job-rag:${var.image_tag}"
      cpu    = var.cpu
      memory = var.memory

      # KV-backed secrets routed to env vars by name reference
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "LANGFUSE_PUBLIC_KEY"
        secret_name = "langfuse-public-key"
      }
      env {
        name        = "LANGFUSE_SECRET_KEY"
        secret_name = "langfuse-secret-key"
      }
      env {
        name        = "SEEDED_USER_ENTRA_OID"
        secret_name = "seeded-user-entra-oid"
      }
      env {
        name        = "POSTGRES_ADMIN_PASSWORD"
        secret_name = "postgres-admin-password"
      }

      # Literal env vars — DATABASE_URL is composed by docker-entrypoint.sh from
      # POSTGRES_* parts (Phase 3 follow-up to entrypoint.sh tracked in Plan 05
      # README; for now, both Phase 1 init_db and Phase 3 entrypoint expect
      # ASYNC_DATABASE_URL/DATABASE_URL to be pre-composed).
      env {
        name  = "POSTGRES_HOST"
        value = var.postgres_fqdn
      }
      env {
        name  = "POSTGRES_DB"
        value = "jobrag"
      }
      env {
        name  = "POSTGRES_USER"
        value = var.postgres_admin_login
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins # composition layer builds CSV per DEPL-12 two-pass
      }
      env {
        name  = "JOB_RAG_API_KEY"
        value = "" # disabled in prod (Entra JWT replaces it Phase 4)
      }

      # Phase 1 invariants — preserved as inline literals
      env {
        name  = "AGENT_TIMEOUT_SECONDS"
        value = "60" # Phase 1 D-25
      }
      env {
        name  = "HEARTBEAT_INTERVAL_SECONDS"
        value = "15" # Phase 1 BACK-05
      }
      env {
        name  = "SEEDED_USER_ID"
        value = var.seeded_user_id # Adrian's UUID per Phase 1 D-08
      }

      # ─── Phase 4 D-04 — auth-related plain env vars ──────────────────────
      # Public-by-design per Phase 3 D-13 (KV reserved for genuine secrets).
      # SEEDED_USER_ENTRA_OID (the secret of the four) is wired ABOVE via
      # secret_name = "seeded-user-entra-oid" (KV secretRef from existing
      # Phase 3 D-09 placeholder slot).
      env {
        name  = "BACKEND_AUDIENCE"
        value = var.backend_audience
      }
      env {
        name  = "ENTRA_TENANT_ID"
        value = var.entra_tenant_id
      }
      env {
        name  = "ENTRA_TENANT_SUBDOMAIN"
        value = var.entra_tenant_subdomain
      }
    }

    http_scale_rule {
      # Without an explicit rule, ACA tears replicas down between requests,
      # so new revisions never stay warm long enough for the activation
      # probe to declare Healthy — deploys silently fall back to the last
      # Healthy revision while CI reports success.
      name                = "http"
      concurrent_requests = "10"
    }
  }

  tags = var.tags
}
