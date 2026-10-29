# Root terragrunt.hcl - Common configuration for all AWS modules
#
# This file is included by all module terragrunt.hcl files and provides:
# - Remote state configuration (S3 + DynamoDB)
# - Provider generation (AWS + AWSCC)
# - Common inputs

locals {
  # Environment defaults (can be overridden per-module)
  environment = "dev"
  aws_region  = "us-east-1"

  # Common tags applied to all resources
  common_tags = {
    Environment = local.environment
    ManagedBy   = "terragrunt"
    Project     = "agentcore-runtime"
    Repository  = "template-repo"
  }
}

# Remote state configuration using S3 + DynamoDB for locking
remote_state {
  backend = "s3"
  config = {
    bucket         = "terraform-state-agentcore-${get_aws_account_id()}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "terraform-locks-agentcore"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

provider "aws" {
  region = "${local.aws_region}"

  default_tags {
    tags = ${jsonencode(local.common_tags)}
  }
}

provider "awscc" {
  region = "${local.aws_region}"
}
EOF
}

# Common inputs for all modules
inputs = {
  aws_region  = local.aws_region
  environment = local.environment
  common_tags = local.common_tags
}
