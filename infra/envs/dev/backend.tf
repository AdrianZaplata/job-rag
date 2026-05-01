terraform {
  required_version = ">= 1.9"

  backend "azurerm" {
    # PLACEHOLDERS — replace with bootstrap output values per infra/bootstrap/README.md Step 3.
    # Real values look like: storage_account_name = "jobragtfstateab123" (yours will differ).
    # Same backend as prod; different `key` so dev state lives in a separate blob.
    resource_group_name  = "jobrag-tfstate-rg"
    storage_account_name = "jobragtfstateq7u9r"
    container_name       = "tfstate"
    key                  = "dev.tfstate"
    use_azuread_auth     = true
  }
}
