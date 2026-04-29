plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "azurerm" {
  enabled = true
  version = "0.27.0"
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

# Enforce naming convention from CONTEXT.md Discretion: jobrag-{env}-{kind}
config {
  format = "compact"
  call_module_type = "all"
}

# Module versions are pinned in main.tf; tflint warns if the pin is missing
rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}

rule "terraform_unused_declarations" {
  enabled = true
}
