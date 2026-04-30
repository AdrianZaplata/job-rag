terraform {
  required_version = ">= 1.9"

  backend "azurerm" {
    # PLACEHOLDERS — replace with bootstrap output values per infra/bootstrap/README.md Step 3.
    # Real values look like: storage_account_name = "jobragtfstateab123" (yours will differ).
    resource_group_name  = "jobrag-tfstate-rg"
    storage_account_name = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
    container_name       = "tfstate"
    key                  = "prod.tfstate"
    use_azuread_auth     = true
  }
}
