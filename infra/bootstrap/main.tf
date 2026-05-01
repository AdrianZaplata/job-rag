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

# Identity of the principal running `terraform apply` here (Adrian).
# Used to grant blob-data RBAC on the tfstate container so AAD-auth backend works.
data "azurerm_client_config" "current" {}

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

  # NOTE: shared_access_key_enabled is left at the provider default (true) for now.
  # Future hardening: flip to false to force AAD-only. That requires also setting
  # `storage_use_azuread = true` on the azurerm provider AND granting the deployer
  # Storage Queue Data Contributor + Storage File Data Privileged Contributor in
  # addition to Blob Data Contributor (the provider refreshes queue/share/blob
  # service properties on every plan, and AAD must cover all three). Tracked as
  # a follow-up hardening — backend already uses use_azuread_auth=true regardless,
  # so TF state itself never travels the shared-key path.

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

# Grant Adrian (the bootstrap apply principal) the blob-data role he needs to
# read/write tfstate via AAD auth from infra/envs/prod/. Scoped to the container,
# not the storage account — principle of least privilege. Required because
# subscription-Owner (management plane) does NOT imply blob-data access (data plane).
resource "azurerm_role_assignment" "deployer_tfstate_blob_data_contributor" {
  scope                = azurerm_storage_container.tfstate.resource_manager_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
  description          = "Grants the bootstrap deployer (Adrian) read/write access to terraform state blobs via AAD auth."
}
