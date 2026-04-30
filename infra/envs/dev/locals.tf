locals {
  prefix = "jobrag-dev"

  tags = {
    project    = "job-rag"
    env        = "dev"
    managed_by = "terraform"
  }

  # DEPL-12 two-pass CORS pattern — mirror of prod (B1: empty-string + compact()).
  # Dev never applies in v1 (D-04), but the local stays for structural parity so
  # `terraform validate` exercises the same wiring as prod.
  allowed_origins_csv = join(",", compact([
    var.swa_origin == "" ? "" : var.swa_origin,
    "http://localhost:5173",
  ]))
}
