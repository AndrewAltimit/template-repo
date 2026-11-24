# VPC with public subnets in several zones, no inbound access, S3 gateway endpoint.
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/network"
}

inputs = {
  az_count = 3
}
