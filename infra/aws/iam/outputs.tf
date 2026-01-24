output "deployer_role_arn" {
  description = "ARN of the deployer IAM role"
  value       = aws_iam_role.deployer.arn
}

output "deployer_role_name" {
  description = "Name of the deployer IAM role"
  value       = aws_iam_role.deployer.name
}

output "runtime_execution_role_arn" {
  description = "ARN of the runtime execution IAM role"
  value       = aws_iam_role.runtime_execution.arn
}

output "runtime_execution_role_name" {
  description = "Name of the runtime execution IAM role"
  value       = aws_iam_role.runtime_execution.name
}
