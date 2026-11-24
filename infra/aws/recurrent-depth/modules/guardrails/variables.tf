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

variable "default_max_hours" {
  description = "Lifetime for a Project-tagged instance with no MaxHours tag."
  type        = number
  default     = 4
}

variable "hard_cap_hours" {
  description = "No Project-tagged instance lives longer than this, whatever its tags say."
  type        = number
  default     = 12

  validation {
    condition     = var.hard_cap_hours > 0 && var.hard_cap_hours <= 24
    error_message = "hard_cap_hours must be between 0 and 24."
  }
}

variable "grace_minutes" {
  description = "Extra time past the limit before the reaper acts, so the node's own watchdog goes first."
  type        = number
  default     = 15
}

variable "reaper_interval_minutes" {
  description = "How often the reaper runs."
  type        = number
  default     = 5

  validation {
    condition     = var.reaper_interval_minutes >= 2 && var.reaper_interval_minutes <= 60
    error_message = "reaper_interval_minutes must be between 2 and 60 (rate() needs the plural form)."
  }
}

variable "reaper_dry_run" {
  description = "Log what would be terminated without terminating it."
  type        = bool
  default     = false
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget for the account."
  type        = number
  default     = 500
}

variable "alert_emails" {
  description = "Budget alert recipients. Empty: no budget is created."
  type        = list(string)
  default     = []
}
