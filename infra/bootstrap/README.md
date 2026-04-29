# Infra Bootstrap

> One-time, runs LOCAL state. Creates the Azure Storage account that hosts state for `infra/envs/{prod,dev}/`. The Entra External tenant is also imported here (manually created via portal first per D-05; Microsoft has no first-class Terraform resource for tenant creation in `azuread ~> 3.x`).

**Last verified:** _filled by Plan 02_

---

## Step 1 — Create the Entra External tenant (manual, ~5 min)

_Plan 02 fills the portal click-path. PITFALLS §1 reminder: External ID admin UX is changing — re-verify against current portal._

## Step 2 — Run bootstrap Terraform

_Plan 02 fills concrete commands._

## Step 3 — Capture outputs into `envs/{prod,dev}/backend.tf`

_Plan 02 fills concrete commands._

## Step 4 — `terraform import` the External tenant

_Plan 02 fills concrete commands per D-05._

---

## Knowingly-accepted security trade-offs

_Plan 02 / Plan 04 fill the trade-off table referencing A1 Path A._
