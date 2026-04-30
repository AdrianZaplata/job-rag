locals {
  prefix = "jobrag-prod"

  tags = {
    project    = "job-rag"
    env        = "prod"
    managed_by = "terraform"
  }

  # DEPL-12 two-pass CORS pattern.
  # First apply: var.swa_origin == "" → compact() drops it → only localhost.
  # Second apply (after scripts/refresh-swa-origin.sh): swa_origin is real → both.
  # B1 alignment: use empty-string + compact() (NOT null), matches identity module.
  allowed_origins_csv = join(",", compact([
    var.swa_origin == "" ? "" : var.swa_origin,
    "http://localhost:5173",
  ]))
}
