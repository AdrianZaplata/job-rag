terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # NO backend block — bootstrap intentionally uses LOCAL state (D-02).
  # Local terraform.tfstate is gitignored via Plan 01's .gitignore additions.
}

provider "azurerm" {
  features {}
}

# azuread default provider targets the workforce tenant (Adrian's subscription home tenant)
# per CONTEXT.md Plan-Locking Addendum A4. The External tenant uses an aliased provider
# in identity.tf so the two are clearly separated.
provider "azuread" {}

# Five-char random suffix to satisfy storage account global uniqueness (3-24 chars,
# lowercase alphanumeric).
resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
  numeric = true
}

resource "azurerm_resource_group" "tfstate" {
  name     = "jobrag-tfstate-rg"
  location = "westeurope"
  tags = {
    project    = "job-rag"
    managed_by = "terraform-bootstrap"
  }
}

resource "azurerm_storage_account" "tfstate" {
  name                     = "jobragtfstate${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Versioning + 7-day soft delete protect against state corruption / accidental deletion
  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }
  }

  tags = {
    project    = "job-rag"
    managed_by = "terraform-bootstrap"
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}
