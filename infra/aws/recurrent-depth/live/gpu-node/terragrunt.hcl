# Launch templates per tier. No instances: scripts/node.sh launches one per run.
include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/gpu-node"
}

dependency "results_store" {
  config_path                             = "../results-store"
  mock_outputs                            = { bucket_name = "recurrent-depth-results-dev-mock" }
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "network" {
  config_path                             = "../network"
  mock_outputs                            = { security_group_id = "sg-00000000000000000", subnet_ids = { "us-east-1a" = "subnet-00000000000000000" } }
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "node_iam" {
  config_path                             = "../node-iam"
  mock_outputs                            = { instance_profile_name = "recurrent-depth-dev-node" }
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

inputs = {
  bucket_name           = dependency.results_store.outputs.bucket_name
  security_group_id     = dependency.network.outputs.security_group_id
  instance_profile_name = dependency.node_iam.outputs.instance_profile_name
  # The emulator has no public Deep Learning AMI parameter; use any registered image id there.
  ami_id = include.root.locals.is_emulator ? get_env("RDS_EMULATOR_AMI", "ami-00000000000000017") : null
}
