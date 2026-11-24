# root.hcl - shared Terragrunt configuration for the recurrent-depth measurement stack.
#
# Separate from ../root.hcl (AgentCore): its own state, tags and provider setup.
#
# Two targets, chosen with RDS_TARGET:
#   aws       (default) real AWS; remote state in S3 with native lock files
#   emulator  the local AWS Emulator on https://127.0.0.1:9297; local state,
#             every service endpoint pointed at the emulator, dummy credentials
#
# Nothing here deploys by itself. See README.md for the order of operations.

locals {
  target      = get_env("RDS_TARGET", "aws")
  is_emulator = local.target == "emulator"
  environment = get_env("RDS_ENVIRONMENT", "dev")
  aws_region  = get_env("AWS_REGION", "us-east-1")
  project     = "recurrent-depth"

  emulator_endpoint = get_env("RDS_EMULATOR_ENDPOINT", "https://127.0.0.1:9297")

  # Set by scripts/infra.sh from the caller's account id (rds-tfstate-<account>-<region>).
  # Read from the environment rather than get_aws_account_id() so emulator runs never call real STS.
  state_bucket = get_env("RDS_STATE_BUCKET", "rds-tfstate-unset")

  common_tags = {
    Project     = local.project
    Environment = local.environment
    ManagedBy   = "terragrunt"
    Repository  = "template-repo"
  }

  # Services the stack uses; each is routed to the emulator in emulator mode.
  emulated_services  = ["budgets", "cloudwatch", "cloudwatchlogs", "ec2", "events", "iam", "lambda", "s3", "ssm", "sts"]
  emulator_endpoints = join("\n", [for s in local.emulated_services : "    ${s} = \"${local.emulator_endpoint}\""])

  provider_emulator = <<-EOT
provider "aws" {
  region                      = "${local.aws_region}"
  access_key                  = "emulator"
  secret_key                  = "emulator"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true

  endpoints {
${local.emulator_endpoints}
  }

  default_tags {
    tags = ${jsonencode(local.common_tags)}
  }
}
EOT

  provider_real = <<-EOT
provider "aws" {
  region = "${local.aws_region}"

  default_tags {
    tags = ${jsonencode(local.common_tags)}
  }
}
EOT

  backend_emulator = <<-EOT
terraform {
  backend "local" {
    path = "${get_parent_terragrunt_dir()}/.emulator-state/${path_relative_to_include()}/terraform.tfstate"
  }
}
EOT

  backend_real = <<-EOT
terraform {
  backend "s3" {
    bucket       = "${local.state_bucket}"
    key          = "${local.environment}/${path_relative_to_include()}/terraform.tfstate"
    region       = "${local.aws_region}"
    encrypt      = true
    use_lockfile = true
  }
}
EOT
}

# Real AWS: S3 state with S3-native locking (Terraform 1.10+, no DynamoDB table).
# The bucket is created once by scripts/infra.sh bootstrap-state.
# Emulator: local state in .emulator-state/ (gitignored), discarded with the emulator.
# Written as a generated file rather than remote_state so the two targets can
# differ in shape without HCL type unification.
generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = local.is_emulator ? local.backend_emulator : local.backend_real
}

# Provider settings only. Each module declares its own required_providers in
# versions.tf so it can also be tested on its own with `terraform test`.
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = local.is_emulator ? local.provider_emulator : local.provider_real
}

inputs = {
  project     = local.project
  environment = local.environment
  aws_region  = local.aws_region
  emulator    = local.is_emulator
}
