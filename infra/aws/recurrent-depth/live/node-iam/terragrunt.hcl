# Instance role: read bundles and weights, write checkpoints, never delete.
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/node-iam"
}

dependency "results_store" {
  config_path                             = "../results-store"
  mock_outputs                            = { bucket_name = "recurrent-depth-results-dev-mock" }
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

inputs = {
  bucket_name = dependency.results_store.outputs.bucket_name
  enable_ssm  = get_env("RDS_ENABLE_SSM", "false") == "true"
}
