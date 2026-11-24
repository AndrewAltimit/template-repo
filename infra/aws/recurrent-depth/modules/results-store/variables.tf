variable "project" {
  description = "Project name used in resource names and tags."
  type        = string
  default     = "recurrent-depth"
}

variable "environment" {
  description = "Environment name (dev, prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "emulator" {
  description = "True when applying against the local AWS Emulator; skips resources it does not implement."
  type        = bool
  default     = false
}

variable "bucket_name" {
  description = "Explicit bucket name. Default: <project>-results-<environment>-<name_suffix>."
  type        = string
  default     = null
}

variable "name_suffix" {
  description = "Suffix that makes the default bucket name globally unique (for example the account id)."
  type        = string
  default     = "local"

  validation {
    condition     = can(regex("^[a-z0-9-]{1,20}$", var.name_suffix))
    error_message = "name_suffix must be 1-20 lowercase letters, digits or hyphens."
  }
}

variable "force_destroy" {
  description = "Allow destroying the bucket while it still holds objects. Keep false outside tests."
  type        = bool
  default     = false
}

variable "noncurrent_version_days" {
  description = "Days to keep overwritten or deleted object versions."
  type        = number
  default     = 30

  validation {
    condition     = var.noncurrent_version_days >= 1
    error_message = "noncurrent_version_days must be at least 1."
  }
}

variable "weights_retention_days" {
  description = "Days to keep the weights/ mirror before it expires (storage for 750 GB is about $17 a month)."
  type        = number
  default     = 14

  validation {
    condition     = var.weights_retention_days >= 1 && var.weights_retention_days <= 365
    error_message = "weights_retention_days must be between 1 and 365."
  }
}
