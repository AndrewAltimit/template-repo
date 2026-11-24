output "launch_templates" {
  description = "Launch template id, name and hard cap per tier, for scripts/node.sh."
  value = {
    for tier, lt in aws_launch_template.node : tier => {
      id            = lt.id
      name          = lt.name
      instance_type = lt.instance_type
      max_hours     = var.tiers[tier].max_hours
    }
  }
}

output "bootstrap_scripts" {
  description = "Rendered bootstrap script per tier (for tests and review; marked sensitive only to keep it out of apply logs)."
  value       = local.bootstrap
  sensitive   = true
}
