terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
  }
}

# Azure Container Apps environment — Consumption tier (default; no workload_profile block).
# Per CONTEXT.md A1 we accept that Consumption-tier outbound IP is not guaranteed static;
# Postgres firewall uses 0.0.0.0 "Allow Azure services" + TLS + 32-char password as the
# security boundary. NAT Gateway + Workload Profiles deferred to v2 paid tier.
resource "azurerm_container_app_environment" "main" {
  name                       = "jobrag-${var.env}-aca-env"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id

  tags = var.tags
}
