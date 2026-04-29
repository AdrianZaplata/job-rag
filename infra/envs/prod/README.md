# Prod environment

> Active production environment for the job-rag stack.

---

## First apply (pass 1)

_Plan 04 fills concrete commands._

## Two-Pass CORS Bootstrap

_Plan 04 fills the DEPL-12 / A3 sequence using `scripts/refresh-swa-origin.sh`. The first apply leaves `swa_origin = ""` and `ALLOWED_ORIGINS=http://localhost:5173`; the helper reads `terraform output -raw swa_default_origin`, rewrites `prod.tfvars`, and re-runs `apply`._

## Image push and ACA revision update

_Plan 07 (deploy-api.yml) describes the GHA-driven path. Plan 04 documents the manual fallback._

## Post-apply smoke checklist

_Plan 08 fills the M1–M13 checklist linked to VALIDATION.md._

## Knowingly-accepted security trade-offs

_Plan 04 fills the table per A1 Path A: 0.0.0.0 firewall rule + TLS + 32-char random password as the security boundary; private endpoint deferred to v2 paid tier._

## Token rotation cadence

_Plan 04 fills the SWA api_key 180-day rotation cadence + GHA secret update procedure._
