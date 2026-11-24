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
  type    = bool
  default = false
}

variable "bucket_name" {
  description = "Results bucket (bundles in, checkpoints out)."
  type        = string
}

variable "instance_profile_name" {
  description = "Instance profile from the node-iam module."
  type        = string
}

variable "security_group_id" {
  description = "Node security group from the network module."
  type        = string
}

variable "ami_id" {
  description = "Explicit AMI. Default: resolve ami_ssm_parameter (AWS Deep Learning AMI)."
  type        = string
  default     = null
}

variable "ami_ssm_parameter" {
  description = "Public SSM parameter holding the current Deep Learning Base AMI (NVIDIA driver, Ubuntu 22.04)."
  type        = string
  default     = "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id"
}

variable "root_device_name" {
  description = "Root device of the AMI."
  type        = string
  default     = "/dev/sda1"
}

variable "tiers" {
  description = <<-EOT
    Node tiers. max_hours is the hard cap a launch can ask for; the node powers
    itself off at the requested limit and the reaper terminates anything older
    than this cap. Prices change; check before launching.
  EOT
  type = map(object({
    instance_type  = string
    root_volume_gb = number
    max_hours      = number
    spot           = optional(bool, false)
  }))
  default = {
    # 1x L4 (24 GB): Huginn-0125, Ouro and the 1.7B controls in bf16.
    single-gpu = { instance_type = "g6.xlarge", root_volume_gb = 150, max_hours = 4 }
    # 1x L40S (48 GB): headroom for longer contexts or two models.
    single-gpu-large = { instance_type = "g6e.xlarge", root_volume_gb = 200, max_hours = 4 }
    # 8x H200 (1.1 TB HBM) plus 8 local NVMe drives: GLM-5.x in FP8.
    frontier = { instance_type = "p5en.48xlarge", root_volume_gb = 200, max_hours = 8 }
  }

  validation {
    condition     = alltrue([for t in values(var.tiers) : t.max_hours > 0 && t.max_hours <= 12])
    error_message = "every tier needs max_hours between 0 and 12."
  }

  validation {
    condition     = alltrue([for k in keys(var.tiers) : can(regex("^[a-z0-9-]{1,32}$", k))])
    error_message = "tier names must be 1-32 lowercase letters, digits or hyphens."
  }
}
