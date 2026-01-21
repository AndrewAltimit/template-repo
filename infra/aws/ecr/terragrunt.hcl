# ECR module for AgentCore runtime images

include "root" {
  path = find_in_parent_folders()
}

inputs = {
  repository_name      = "bedrock-agentcore-strands-runtime-dev"
  image_tag_mutability = "MUTABLE"
  scan_on_push         = true
  max_image_count      = 5

  tags = {
    Module = "ecr"
  }
}
