variable "deployer_role_name" {
  description = "Name of the IAM role for Terraform deployments"
  type        = string
  default     = "AgentCoreDeployer"
}

variable "runtime_execution_role_name" {
  description = "Name of the IAM role for AgentCore runtime execution"
  type        = string
  default     = "AgentCoreRuntimeExecution"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
