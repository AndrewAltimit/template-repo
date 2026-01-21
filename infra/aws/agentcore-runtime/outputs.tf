output "runtime_id" {
  description = "ID of the AgentCore Runtime"
  value       = awscc_bedrockagentcore_runtime.main.agent_runtime_id
}

output "runtime_arn" {
  description = "ARN of the AgentCore Runtime"
  value       = awscc_bedrockagentcore_runtime.main.agent_runtime_arn
}

output "runtime_version" {
  description = "Version of the AgentCore Runtime"
  value       = awscc_bedrockagentcore_runtime.main.agent_runtime_version
}

output "runtime_status" {
  description = "Status of the AgentCore Runtime"
  value       = awscc_bedrockagentcore_runtime.main.status
}

output "log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.runtime.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.runtime.arn
}
