# IAM module for AgentCore

include "root" {
  path = find_in_parent_folders()
}

inputs = {
  deployer_role_name          = "AgentCoreDeployer-dev"
  runtime_execution_role_name = "AgentCoreRuntimeExecution-dev"

  tags = {
    Module = "iam"
  }
}
