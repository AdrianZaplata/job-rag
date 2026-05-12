terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
  }
}

# AVM Log Analytics workspace per CONTEXT.md D-03.
# 0.5.1 verified live Dec 23 2025. log_analytics_workspace_daily_quota_gb input
# maps the daily cap (D-16) — keeps free-tier ingest under the 5 GB/mo alert.
module "log_analytics" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                = "jobrag-${var.env}-law"
  location            = var.location
  resource_group_name = var.resource_group_name

  log_analytics_workspace_sku               = "PerGB2018"
  log_analytics_workspace_retention_in_days = 30   # default — Discretion
  log_analytics_workspace_daily_quota_gb    = 0.15 # D-16 — ≈4.5 GB/mo, 90% of DEPL-10's 5GB alert

  # Gap 12.A: AVM avm-res-operationalinsights-workspace 0.5.1 defaults both
  # publicNetworkAccessForIngestion and publicNetworkAccessForQuery to Disabled
  # when no override is supplied, which blocks ACA Console Logs ingestion AND
  # Adrian local az monitor log-analytics query from his home IP (Test 10 / 12
  # NspValidationFailedError). Restoring public access matches the free-tier
  # posture (DEPL-10 intent) and CONTEXT.md A1 Path A precedent (TLS + scoped
  # auth, not network isolation, is the boundary).
  log_analytics_workspace_internet_ingestion_enabled = true
  log_analytics_workspace_internet_query_enabled     = true

  tags = var.tags
}

# NOTE: azurerm_monitor_diagnostic_setting is intentionally NOT defined here.
# Diagnostic settings reference a target resource (ACA) created at the composition
# layer, so they MUST live at the composition layer (envs/{env}/main.tf), not in
# this module. See README.md "Where diagnostic_setting lives" for the rationale.
# Defining it here AND at composition would cause a duplicate-resource conflict.

# W1 fix: use data source for subscription resource ID (auto-prefixed with /subscriptions/).
# Avoids manual var.subscription_id formatting (off-by-one risk on /subscriptions/ prefix).
data "azurerm_subscription" "current" {}

# Consumption budget at subscription scope — €10/mo per CONTEXT.md D-18 + DEPL-11.
# Thresholds 50/75/90/100% catch runaway resources at €5 not €10.
# (Only created when var.create_budget = true so dev scaffold doesn't fight prod
# for the single subscription-scoped budget — there is exactly one prod budget.)
resource "azurerm_consumption_budget_subscription" "prod" {
  count = var.create_budget ? 1 : 0

  name            = "jobrag-${var.env}-budget"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 10
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
    end_date   = "2030-12-31T23:59:59Z"
  }

  dynamic "notification" {
    for_each = toset([50, 75, 90, 100])

    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThan"
      threshold_type = "Actual"
      contact_emails = [var.budget_alert_email]
    }
  }

  lifecycle {
    ignore_changes = [time_period[0].start_date] # avoid plan churn on month rollover
  }
}
