# Reaper Lambda (terminates Project-tagged nodes past their limit) and a monthly budget.
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/guardrails"
}

inputs = {
  hard_cap_hours     = 12
  monthly_budget_usd = tonumber(get_env("RDS_MONTHLY_BUDGET_USD", "500"))
  # Comma-separated; empty means no budget is created.
  alert_emails = compact(split(",", get_env("RDS_ALERT_EMAILS", "")))
}
