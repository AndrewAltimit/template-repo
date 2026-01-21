# AgentCore Runtime module

include "root" {
  path = find_in_parent_folders()
}

# Dependencies - runtime needs IAM and ECR to be deployed first
dependency "iam" {
  config_path = "../iam"

  mock_outputs = {
    runtime_execution_role_arn = "arn:aws:iam::123456789012:role/mock-role"
  }
}

dependency "ecr" {
  config_path = "../ecr"

  mock_outputs = {
    repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/mock-repo"
  }
}

inputs = {
  # Note: AgentCore runtime names must use underscores, not hyphens
  runtime_name       = "strands_agent_runtime_dev"
  description        = "Strands-based AI agent runtime (dev)"
  container_uri      = "${dependency.ecr.outputs.repository_url}:latest"
  runtime_role_arn   = dependency.iam.outputs.runtime_execution_role_arn
  network_mode       = "PUBLIC"
  protocol           = "HTTP"
  log_level          = "DEBUG"
  log_retention_days = 7

  environment_variables = {
    ENVIRONMENT = "dev"
  }

  tags = {
    Module = "agentcore-runtime"
  }
}
