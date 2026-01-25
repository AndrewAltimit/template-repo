variable "runtime_name" {
  description = "Name of the AgentCore Runtime"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,47}$", var.runtime_name))
    error_message = "Runtime name must start with a letter and contain only alphanumeric characters and underscores (max 48 chars)"
  }
}

variable "description" {
  description = "Description of the AgentCore Runtime"
  type        = string
  default     = "Strands-based AI agent runtime"
}

variable "container_uri" {
  description = "ECR container URI for the runtime image"
  type        = string
}

variable "runtime_role_arn" {
  description = "ARN of the IAM role for runtime execution"
  type        = string
}

variable "network_mode" {
  description = "Network mode for the runtime (PUBLIC or PRIVATE)"
  type        = string
  default     = "PUBLIC"
}

variable "protocol" {
  description = "Communication protocol (HTTP, MCP, or A2A)"
  type        = string
  default     = "HTTP"
}

variable "log_level" {
  description = "Log level for the runtime"
  type        = string
  default     = "INFO"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "environment_variables" {
  description = "Additional environment variables for the runtime"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
