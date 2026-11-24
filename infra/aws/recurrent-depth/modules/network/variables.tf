variable "project" {
  type    = string
  default = "recurrent-depth"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "emulator" {
  description = "True when applying against the local AWS Emulator."
  type        = bool
  default     = false
}

variable "vpc_cidr" {
  description = "VPC CIDR block; subnets are /24 slices of it."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && tonumber(split("/", var.vpc_cidr)[1]) <= 20
    error_message = "vpc_cidr must be a valid CIDR of /20 or larger."
  }
}

variable "availability_zones" {
  description = "Zones to create subnets in. Empty: the first az_count available zones."
  type        = list(string)
  default     = []
}

variable "az_count" {
  description = "Number of zones when availability_zones is empty."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 1 && var.az_count <= 6
    error_message = "az_count must be between 1 and 6."
  }
}
