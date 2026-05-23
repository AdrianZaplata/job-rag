---
status: resolved
trigger: "Phase 04.1 UAT Test 2 — `terraform plan -var-file=terraform.tfvars.local` halts with `Error: Self-referential block` on `infra/external/main.tf:32` (identifier_uris = [\"api://${azuread_application.api.client_id}\"])"
created: 2026-05-23T11:00:00Z
updated: 2026-05-23T20:55:00Z
resolved_by: 04.1-06-PLAN.md (commits 96e7b9f code+docs + b2ee4fe UAT Test 2 pass; operator-verified live sign-in PASS post-apply)
---

## Current Focus

hypothesis: "Plan 04.1-05 attempted a structural refactor that the azuread provider does not support: setting `identifier_uris` inline on `azuread_application` to a value derived from that same resource's `client_id` is forbidden by Terraform's resource-graph rule against self-reference. `terraform validate` passed (schema-level check — `identifier_uris` IS a valid attribute on the resource) but `terraform plan` (which runs the graph-level evaluation) fails on the self-reference. The deeper issue is that the original Phase 4 problem (`azuread_application_identifier_uri` silently leaves the live list empty) is real, and there is no inline workaround — the canonical fix is to split the application using the provider's purpose-built lightweight resource `azuread_application_registration` (which is decomposable and is the documented partner of `azuread_application_identifier_uri`)."
test: "Run `terraform validate` and `terraform plan` on current main.tf; cross-reference azuread provider 3.x docs for `azuread_application_registration`; verify downstream consumers via grep."
expecting: "validate exits 0 (schema valid), plan exits 1 with self-ref error (confirms graph-level violation); docs confirm `azuread_application_registration` is the decomposable replacement; downstream consumers (frontend/.env.production, prod.tfvars.local, refresh-external-outputs.sh) all read api_audience_uri as `api://<api_client_id>` literal string."
next_action: "Return diagnosis to plan-phase --gaps so planner can scope the structural fix."

## Symptoms

expected: "`cd infra/external && terraform apply -var-file=terraform.tfvars.local` produces a clean plan + apply where `azuread_application_identifier_uri.api` is destroyed and `azuread_application.api` is updated in-place with `identifier_uris = [\"api://${client_id}\"]`, and `az ad app show --id ${client_id} --query identifierUris -o tsv` returns the populated `api://...` URI."
actual: "terraform plan fails with `Error: Self-referential block on main.tf line 32` — `Configuration for azuread_application.api may not refer to itself.` Plan output is `Plan: 0 to add, 0 to change, 1 to destroy.` (the destroy of the standalone identifier_uri resource is planned correctly) but apply is never attempted because the parse-level evaluation aborts."
errors: "Error: Self-referential block / on main.tf line 32, in resource \"azuread_application\" \"api\" / 32:   identifier_uris = [\"api://${azuread_application.api.client_id}\"] / Configuration for azuread_application.api may not refer to itself."
reproduction: "cd infra/external && terraform plan -var-file=terraform.tfvars.local"
started: "Introduced by commit 7e0718c (Phase 04.1 plan 05, 2026-05-21). Surfaced during Phase 04.1 UAT 2026-05-23."

## Eliminated

- hypothesis: "The `identifier_uris` attribute is not supported on `azuread_application` v3.x"
  evidence: "`terraform validate` exits 0 — the attribute IS in the schema. Confirmed via provider docs (registry.terraform.io/providers/hashicorp/azuread/latest/docs/resources/application). The provider accepts the attribute; the failure is at the graph/expression evaluation layer, not the schema layer."
  timestamp: 2026-05-23T11:20:00Z

- hypothesis: "Provider lock file is stuck on an old version that doesn't support the attribute"
  evidence: ".terraform.lock.hcl shows azuread v3.8.0 — latest 3.x line. Attribute is documented for this version."
  timestamp: 2026-05-23T11:21:00Z

- hypothesis: "Plan 04.1-05's pre-commit verification (terraform validate exit 0) was sufficient to prove correctness"
  evidence: "It was not. `terraform validate` does NOT run the resource graph evaluator; it only checks HCL syntax + provider schema. The self-reference rule is a graph-level invariant evaluated during `terraform plan`. The plan author conflated 'validate passes' with 'plan passes' and the SUMMARY (line 245 of 04.1-05-PLAN.md) explicitly claimed that self-references on computed attributes are 'fine' — they are not, when the computed attribute belongs to the resource itself."
  timestamp: 2026-05-23T11:22:00Z

## Evidence

- timestamp: 2026-05-23T11:05:00Z
  checked: "infra/external/main.tf line 32"
  found: "identifier_uris = [\"api://${azuread_application.api.client_id}\"] — direct self-reference inside the `azuread_application.api` resource block"
  implication: "Plan 04.1-05's structural premise (inline attribute is the reliable form for `api://<client_id>`) is invalid for the case where the URI is derived from the application's own client_id. Inline works for static URIs (`api://booking`, `https://app.example.com`) but cannot resolve `${self.client_id}` because the resource hasn't been created yet at plan time."

- timestamp: 2026-05-23T11:10:00Z
  checked: "infra/external/outputs.tf"
  found: "Both `api_audience_uri.value` (line 17) and `api_scope_name.value` (line 22) now read `one(azuread_application.api.identifier_uris)` — they also depend on the broken inline attribute, so the same `terraform plan` error blocks any downstream consumer refresh."
  implication: "outputs.tf must be rewired as part of the fix. Pinned by Plan 04.1-05's Rule-1 auto-fix decision (3-file commit)."

- timestamp: 2026-05-23T11:11:00Z
  checked: "terraform state list && terraform state show azuread_application_identifier_uri.api"
  found: "Standalone resource is in state with `identifier_uri = \"api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20\"`. State currently holds the working live value — the workaround `az ad app update` from Phase 4 must have populated the Azure live list, and Terraform refresh pulled it into state. The destroy plan in the failed run is asking to remove this state row (correct) but the inline replacement on the application resource never gets a chance to run."
  implication: "If we revert to the original standalone-resource form (no inline), the standalone resource is already in state and live; one possible recovery is `terraform plan` against the original Plan 4.0 main.tf (which would show zero diff because state matches Azure). But the original motivation for removal — silent-fail on fresh apply — remains documented."

- timestamp: 2026-05-23T11:15:00Z
  checked: "Memory `terraform-azuread-identifier-uri-unreliable.md`"
  found: "Documented failure mode: `azuread_application_identifier_uri` 'reports successful apply but DOES NOT actually populate the application's identifierUris array in Azure.' Detected during Phase 4 (2026-05-21). Workaround: verify post-apply with `az ad app show --query identifierUris`, unblock with `az ad app update --identifier-uris ...`. This is the original-problem statement Plan 04.1-05 tried to fix structurally."
  implication: "A naive revert to the standalone resource is NOT acceptable: it brings back the silent-fail risk for fresh apply. The fix must address BOTH the self-reference error AND the original silent-fail risk."

- timestamp: 2026-05-23T11:18:00Z
  checked: "Web search: 'azuread_application identifier_uris self-reference client_id'"
  found: "Confirmed via hashicorp/terraform-provider-azuread GitHub issue #428 — this is a long-known circular-dependency problem with `identifier_uris = [\"api://${self.client_id}\"]`. Issue proposed (and later closed in v2.44.0) auto-defaulting the field to `api://<application_id>` when unset — but ONLY when the attribute is OMITTED entirely (cannot be `[]` or any other value). Setting it explicitly with a self-reference is unsupported by design."
  implication: "There is no inline workaround for the `${self.client_id}` case. The provider's `azuread_application_registration` resource (documented at registry.terraform.io/providers/hashicorp/azuread/latest/docs/resources/application_registration) is the lightweight, decomposable replacement specifically designed to work alongside the `azuread_application_*` sub-resources (including `azuread_application_identifier_uri`). The split pattern is the canonical fix."

- timestamp: 2026-05-23T11:20:00Z
  checked: "infra/external/main.tf lines 34-46 (the `api { … }` nested block including `requested_access_token_version = 2` and `oauth2_permission_scope`)"
  found: "These features (token version 2, API scope) are NOT supported on `azuread_application_registration` directly — they require the full `azuread_application` resource. The provider's intended decomposition: `azuread_application_registration` for the base + sibling resources like `azuread_application_api_access`, `azuread_application_identifier_uri`, `azuread_application_permission_scope` for each feature axis."
  implication: "A clean split requires THREE resources (or more): `azuread_application_registration.api` (base) + `azuread_application_identifier_uri.api` (URI) + `azuread_application_api_access.api` (token version + scope wiring). This is a larger refactor than Plan 04.1-05 envisioned."

- timestamp: 2026-05-23T11:22:00Z
  checked: "Downstream consumers — frontend/.env.production:8, infra/envs/prod/prod.tfvars.local:1, scripts/refresh-external-outputs.sh"
  found: "VITE_API_AUDIENCE=api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20 (literal). backend_audience=\"api://a12dfd07-4a63-4edd-9dd0-593aa7ecca20\" (literal). refresh-external-outputs.sh reads `terraform output -raw api_audience_uri` and rewrites both files in place. src/job_rag/api/auth.py line 72 does `settings.backend_audience.removeprefix(\"api://\")` to derive the app_client_id for fastapi-azure-auth — so backend code assumes the `api://` prefix. frontend/src/auth/scopes.ts accepts either with/without prefix already."
  implication: "Backend code (auth.py) DEPENDS on the `api://<guid>` shape — it strips `api://` and uses the remainder as the API app's client_id. Switching to a static URI like `api://jobrag-prod` would break this contract (no client_id to extract). The URI format is load-bearing: it MUST be `api://<api_client_id>` for the backend to validate JWTs."

- timestamp: 2026-05-23T11:25:00Z
  checked: "Provider behavior for `azuread_application_registration` + sibling resources"
  found: "Per provider docs: `azuread_application_registration` exposes `client_id` as a computed attribute the same way `azuread_application` does. Other resources (including `azuread_application_identifier_uri`) accept an `application_id` referencing either the full `azuread_application` resource OR the lightweight `azuread_application_registration`. Critically, `azuread_application_identifier_uri.api` referencing `azuread_application_registration.api.client_id` is a CROSS-resource reference, NOT a self-reference — so Terraform's graph rule does not apply."
  implication: "The split pattern resolves the self-reference error mechanically: the URI computation `api://${azuread_application_registration.api.client_id}` lives in a DIFFERENT resource (`azuread_application_identifier_uri.api`), and Terraform can sequence the create operations correctly (registration first, then URI side-resource). This is the same shape as the original Plan 04 code, except the base resource is `azuread_application_registration` instead of `azuread_application`."

- timestamp: 2026-05-23T11:28:00Z
  checked: "Silent-fail risk reassessment for the split pattern"
  found: "Memory note says the silent-fail mode is specifically about `azuread_application_identifier_uri` reporting `Created` while live list stays empty. If we restore that exact resource (now paired with `azuread_application_registration`), we re-expose the same risk. Mitigation MUST be added: a post-apply assertion that fails loud if the live list is empty."
  implication: "The fix must include a verification step — either (a) a `null_resource` with `local-exec` calling `az ad app show --query identifierUris -o tsv` and grepping for non-empty (which itself has reliability concerns), OR (b) add the assertion to `scripts/refresh-external-outputs.sh` so the next post-apply paste step catches the silent-fail and aborts before downstream files are updated with stale (or empty) values. Option (b) is cleaner — it keeps Terraform itself free of CLI shell-outs, and the assertion runs at the moment any consumer reads the output."

## Resolution

root_cause: |
  Plan 04.1-05 made a structurally invalid change. The inline form
  `identifier_uris = ["api://${azuread_application.api.client_id}"]` inside the
  `azuread_application.api` resource block is a self-reference forbidden by
  Terraform's resource-graph rule (HCL allows it syntactically — `terraform
  validate` passes — but `terraform plan` rejects it). The plan author
  conflated 'validate passes' with 'plan passes' and explicitly asserted in
  the plan body (line 163 of 04.1-05-PLAN.md) that 'Terraform handles
  self-references through computed attributes' — this is true ONLY for
  cross-resource references, never for a resource referring to its own
  attributes. The deeper architectural error: the original Phase 4 problem
  (azuread_application_identifier_uri silently leaving the live list empty)
  has NO inline workaround in the azuread provider — the documented fix is
  to split into `azuread_application_registration` (lightweight base) +
  `azuread_application_identifier_uri` (side resource) + `azuread_application_api_access` (for the
  oauth2_permission_scope + token version 2 wiring that currently lives in
  the `api { … }` nested block). The plan-05 refactor is unrecoverable as
  written; it must be reverted AND re-architected using the split pattern,
  with the silent-fail risk mitigated by a post-apply assertion in
  `scripts/refresh-external-outputs.sh`.

fix: |
  [Diagnose-only mode — fix not applied. Handed to plan-phase --gaps.]

verification: |
  [Diagnose-only mode — verification not run.]

files_changed: []
