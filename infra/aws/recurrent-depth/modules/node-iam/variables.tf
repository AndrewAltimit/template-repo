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
  description = "Results bucket the nodes read bundles from and write checkpoints to."
  type        = string
}

variable "enable_ssm" {
  description = "Attach AmazonSSMManagedInstanceCore so nodes can be reached with Session Manager."
  type        = bool
  default     = false
}
